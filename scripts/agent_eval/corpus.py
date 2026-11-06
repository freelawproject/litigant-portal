"""
Load frozen content through normal corpus services in a disposable database.
"""

import json
import re
import shutil
from collections.abc import Callable, Generator
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


def setup_django(run: Path | None = None) -> None:
    import os

    import django
    from django.conf import settings

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "litigant_portal.settings")
    if run is not None:
        name = json.loads((run / "manifest.json").read_text())[
            "evaluation_database"
        ]
        if not re.fullmatch(r"agent_eval_[0-9a-f]{32}", name):
            raise ValueError("Invalid evaluation database name.")
        if name == settings.DATABASES["default"]["NAME"]:
            raise ValueError(
                "Evaluation database must differ from the application database."
            )
        settings.DATABASES["default"]["NAME"] = name
        settings.CACHES = {
            "default": {
                "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
                "LOCATION": str(run / "cache"),
            }
        }
        settings.STORAGES = {
            **settings.STORAGES,
            **{
                alias: {
                    "BACKEND": "django.core.files.storage.FileSystemStorage",
                    "OPTIONS": {"location": str(run / "media" / alias)},
                }
                for alias in ("default", "public")
            },
        }
    django.setup()


def snapshot_current() -> dict:
    from litigant_portal.agents.assistant import generate_court_prompt
    from litigant_portal.agents.tools.load_topic_flow import (
        topic_flow_markdown,
    )
    from litigant_portal.app.selectors.site import site_get
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
        "fast_model": site.fast_model,
        "court_context": generate_court_prompt(),
        "enabled_flows": flows,
    }


def fixture_root(run: Path, variant: str) -> Path:
    fixture = yaml.safe_load(
        (run / "references" / "fixtures" / f"{variant}.yml").read_text()
    )
    root = run / "corpora" / variant
    court = root / "courts" / "eval-ohio"
    topic = court / "topics" / TOPIC
    (topic / "flows").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(
        run / "references" / "references" / "corpus" / "variables.yml",
        root / "variables.yml",
    )
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


def install_fixture(root: Path, court: str) -> None:
    from litigant_portal.app.services.corpus import corpus_sync

    corpus_sync(root=root, court=court, strict=True)


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
    run: Path,
    fast_model: str | None = None,
    notify: Callable[[], None] = lambda: None,
) -> Generator[None]:
    """
    Create and migrate a private database, then drop it when the worker exits.
    """
    from django.core.management import call_command
    from django.db import connection, connections
    from psycopg import sql

    from litigant_portal.app.models import Site

    name = json.loads((run / "manifest.json").read_text())[
        "evaluation_database"
    ]
    if (
        not re.fullmatch(r"agent_eval_[0-9a-f]{32}", name)
        or connection.settings_dict["NAME"] != name
    ):
        raise ValueError("Worker is not connected to its evaluation database.")
    state = {"name": name, "created": False, "removed": False}
    path = run / "database.json"
    write_json(path, state)
    notify()
    with connection._nodb_cursor() as cursor:
        cursor.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
        )
    try:
        state["created"] = True
        write_json(path, state)
        notify()
        call_command("migrate", interactive=False, verbosity=0)
        Site.objects.update(fast_model=fast_model)
        yield
    finally:
        connections.close_all()
        with connection._nodb_cursor() as cursor:
            cursor.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(name)
                )
            )
        state["removed"] = True
        write_json(path, state)
        notify()
