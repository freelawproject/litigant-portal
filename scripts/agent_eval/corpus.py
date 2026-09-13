"""
Load fictional content through normal database/file surfaces, not prompts.
"""

import json
from contextlib import contextmanager
from pathlib import Path

import yaml

from .schema import write_json

TOPIC = "eval-chicken-displacement"
MARKER = "Managed by scripts.agent_eval"
SITE_FIELDS = (
    "court_name",
    "jurisdiction_level",
    "state",
    "official_url",
    "official_resources_url",
)


def setup_django():
    import os

    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "litigant_portal.settings")
    django.setup()


def snapshot_current() -> dict:
    from litigant_portal.agents.tools.load_topic_flow import (
        topic_flow_markdown,
    )
    from litigant_portal.app.selectors.site import site_get, site_get_model
    from litigant_portal.app.selectors.topic_flow import (
        topic_flow_find,
        topic_flow_list,
    )

    site = site_get()
    flows = []
    for flow in topic_flow_list():
        full = topic_flow_find(topic_slug=flow.topic.slug, flow_slug=flow.slug)
        flows.append(
            {
                "path": f"{flow.topic.slug}/{flow.slug}",
                "content": topic_flow_markdown(full),
            }
        )
    return {
        "site": {field: getattr(site, field) for field in SITE_FIELDS},
        "fast_model": site_get_model(role="fast"),
        "enabled_flows": flows,
    }


def fixture_root(run: Path, variant: str) -> Path:
    fixture = yaml.safe_load(
        (run / "references" / "fixtures" / f"{variant}.yml").read_text()
    )
    root = run / "corpora" / variant
    court = root / "corpus" / "courts" / "eval-ohio"
    topic = court / "topics" / TOPIC
    (topic / "flows").mkdir(parents=True, exist_ok=True)
    values = {
        court / "court.yml": {
            "name": "Fictional Ohio",
            "court_name": fixture["court_name"],
            "state": "OH",
            "jurisdiction_level": "state",
        },
        topic / "topic.yml": {"title": fixture["topic_title"]},
        topic / "flows" / "protection.yml": {
            "name": fixture["flow_name"],
            "enabled": True,
            "sections": fixture["sections"],
        },
    }
    for path, value in values.items():
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
        )
    return root


def install_fixture(root: Path):
    from django.core.cache import cache
    from django.db import transaction

    from litigant_portal.app.cache import SITE_CACHE_KEY, TOPIC_LIST_CACHE_KEY
    from litigant_portal.app.models import (
        Site,
        Topic,
        TopicFlow,
        TopicFlowSection,
    )

    court = root / "corpus" / "courts" / "eval-ohio"
    metadata = yaml.safe_load((court / "court.yml").read_text())
    topic_path = court / "topics" / TOPIC
    content = yaml.safe_load(
        (topic_path / "flows" / "protection.yml").read_text()
    )
    with transaction.atomic():
        topic, _ = Topic.objects.get_or_create(
            slug=TOPIC, defaults={"description": MARKER}
        )
        if topic.description != MARKER:
            raise ValueError(f"Topic {TOPIC} is not owned by the benchmark.")
        topic.title = yaml.safe_load((topic_path / "topic.yml").read_text())[
            "title"
        ]
        topic.save()
        flow, _ = TopicFlow.objects.get_or_create(
            topic=topic, slug="protection"
        )
        flow.name, flow.enabled = content["name"], True
        flow.save()
        flow.sections.all().delete()
        TopicFlowSection.objects.bulk_create(
            [
                TopicFlowSection(flow=flow, order=i, **section)
                for i, section in enumerate(content["sections"])
            ]
        )
        Site.objects.update(
            **{field: metadata.get(field, "") for field in SITE_FIELDS}
        )
    cache.delete_many([SITE_CACHE_KEY, TOPIC_LIST_CACHE_KEY])


@contextmanager
def fixture_lock():
    from django.db import connection

    locked = False
    try:
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_try_advisory_lock(179, 1887)")
                locked = cursor.fetchone()[0]
                if not locked:
                    raise RuntimeError(
                        "Another benchmark is using corpus fixtures."
                    )
        yield
    finally:
        if locked:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(179, 1887)")


def restore(run: Path):
    with fixture_lock():
        _restore(run)


def _restore(run: Path):
    from django.core.cache import cache

    from litigant_portal.app.cache import SITE_CACHE_KEY, TOPIC_LIST_CACHE_KEY
    from litigant_portal.app.models import Site, TopicFlow

    path = run / "fixture-state.json"
    if not path.exists():
        return
    state = json.loads(path.read_text())
    if state["restored"]:
        return
    Site.objects.update(**state["site"])
    TopicFlow.objects.filter(
        topic__slug=TOPIC, topic__description=MARKER
    ).update(enabled=False)
    cache.delete_many([SITE_CACHE_KEY, TOPIC_LIST_CACHE_KEY])
    state["restored"] = True
    write_json(path, state)


@contextmanager
def corpus_session(
    run: Path, needed: bool, fast_model: str | None = None, notify=lambda: None
):
    """
    Serialize fixture changes and restore site settings on normal interruption.
    """
    if not needed:
        yield
        return
    from litigant_portal.app.models import Site
    from litigant_portal.app.selectors.site import site_get_model

    with fixture_lock():
        site = Site.objects.get()
        write_json(
            run / "fixture-state.json",
            {
                "site": {
                    field: getattr(site, field)
                    for field in (*SITE_FIELDS, "fast_model")
                },
                "original_fast_model": site_get_model(role="fast"),
                "effective_fast_model": fast_model
                or site_get_model(role="fast"),
                "restored": False,
            },
        )
        try:
            # Publish the recovery journal before mutating the database.
            notify()
            if fast_model is not None:
                from django.core.cache import cache

                from litigant_portal.app.cache import SITE_CACHE_KEY

                Site.objects.update(fast_model=fast_model)
                cache.delete(SITE_CACHE_KEY)
            yield
        finally:
            _restore(run)
            notify()
