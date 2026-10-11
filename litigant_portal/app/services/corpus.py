from __future__ import annotations

import logging

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction

from litigant_portal.app.cache import (
    CONTACT_LIST_CACHE_KEY,
    RESOURCE_LIST_CACHE_KEY,
    SITE_CACHE_KEY,
    TOPIC_LIST_CACHE_KEY,
)
from litigant_portal.app.models import (
    Contact,
    Form,
    FormField,
    Resource,
    Topic,
    TopicFlow,
    TopicFlowDeadline,
    TopicFlowFormCondition,
    TopicFlowInterviewPage,
    TopicFlowInterviewVariable,
    TopicFlowLink,
    TopicFlowSection,
    Variable,
)
from litigant_portal.app.models.choices import TopicFlowFormConditionOperator
from litigant_portal.app.selectors.corpus import (
    COURTS_DIR,
    FORMS_DIR,
    CorpusSchema,
    CourtSchema,
    FlowSchema,
    corpus_load,
)
from litigant_portal.app.selectors.site import site_get

from .utils import busts_cache

logger = logging.getLogger(__name__)


def _apply(row, schema, *, exclude: set[str] = frozenset()) -> None:
    """Set each schema field onto the row. ``exclude`` names the fields
    the caller resolves itself (relations, files, display-only)."""
    for field, value in schema.model_dump(exclude=exclude).items():
        setattr(row, field, value)


def _source_row(schema, **fields):
    """Schema fields plus the authored ``id``, stored as ``key`` because
    ``id`` is the row's UUID."""
    return {"key": schema.id, **schema.model_dump(exclude={"id"}), **fields}


def _warn_removed_keys(scope: str, stored, authored) -> None:
    """A stored key that left the corpus may still be cited in threads, so
    its removal is reported. Removing a block can be correct, so this is
    a warning, not a failure."""
    removed = sorted(set(stored) - set(authored) - {""})
    if removed:
        logger.warning(
            "%s: source ids removed from the corpus: %s "
            "(stored citations to them are now stale)",
            scope,
            removed,
        )


def _sync_variables(corpus: CorpusSchema) -> dict[str, Variable]:
    """Upsert every variable by name. Two passes: rows first, then gates,
    so a gate can point at a variable created in the same sync."""
    rows = {v.name: v for v in Variable.objects.all()}
    for name, schema in corpus.variables.items():
        row = rows.get(name) or Variable(name=name)
        _apply(row, schema, exclude={"asked_when"})
        row.in_schema = True
        row.save()
        rows[name] = row
    for name, schema in corpus.variables.items():
        row = rows[name]
        gate = schema.asked_when
        row.asked_when = rows[gate.variable] if gate else None
        row.asked_when_value = gate.value if gate else None
        row.save(
            update_fields=["asked_when", "asked_when_value", "updated_at"]
        )
    return rows


def _form_field(
    form: Form, order: int, mapping, variables: dict[str, Variable]
) -> FormField:
    """Build one FormField row, resolving checked_when to its Variable."""
    when = mapping.checked_when
    return FormField(
        form=form,
        order=order,
        checked_when=variables[when.variable] if when else None,
        checked_when_value=when.value if when else None,
        **mapping.model_dump(exclude={"checked_when"}),
    )


def _file_replace(field_file, name: str, content: bytes) -> None:
    """Store ``content`` as ``name`` in place of the field's current file.

    Also clears the target name: a stray file there (an orphan from a
    prior sync) would otherwise suffix the new name on every sync, since
    storage never overwrites."""
    if field_file:
        field_file.delete(save=False)
    target = field_file.field.generate_filename(field_file.instance, name)
    if field_file.storage.exists(target):
        field_file.storage.delete(target)
    field_file.save(name, ContentFile(content), save=False)


def _sync_forms(
    corpus: CorpusSchema, variables: dict[str, Variable]
) -> dict[str, Form]:
    """Upsert every form by slug, rewriting its stored PDF and replacing
    its field mappings wholesale."""
    rows = {f.slug: f for f in Form.objects.all()}
    for slug, schema in corpus.forms.items():
        form = rows.get(slug) or Form(slug=slug)
        _apply(form, schema, exclude={"fields"})
        _file_replace(
            form.file,
            f"{slug}.pdf",
            (FORMS_DIR / f"{slug}.pdf").read_bytes(),
        )
        form.save()
        form.fields.all().delete()
        FormField.objects.bulk_create(
            _form_field(form, order, mapping, variables)
            for order, mapping in enumerate(schema.fields)
        )
        rows[slug] = form
    return rows


def _sync_site(slug: str, schema: CourtSchema) -> None:
    """Write the court's fields and branding onto the Site singleton. A
    branding file the court no longer names is deleted from storage."""
    site = site_get()
    _apply(site, schema, exclude={"name", "contacts", "resources", "branding"})
    site.branding_name = schema.branding.name
    for field, path in (
        ("logo", schema.branding.logo),
        ("name_image", schema.branding.name_image),
    ):
        field_file = getattr(site, field)
        if path is None:
            if field_file:
                field_file.delete(save=False)
            continue
        source = COURTS_DIR / slug / path
        _file_replace(
            field_file, f"{slug}-{field}{source.suffix}", source.read_bytes()
        )
    site.save(
        update_fields=[
            "court_name",
            "jurisdiction_level",
            "state",
            "official_url",
            "official_resources_url",
            "branding_name",
            "logo",
            "name_image",
            "updated_at",
        ]
    )


def _reject_shared_names(courts: list[CourtSchema]) -> None:
    """Contact names and resource labels are unique columns, so two courts
    in one sync sharing one would collapse into a single row. The schema
    already rejects a repeat within one court, so any repeat here spans
    courts."""
    for scope, values in (
        ("contact names", [c.name for s in courts for c in s.contacts]),
        ("resource labels", [r.label for s in courts for r in s.resources]),
    ):
        shared = sorted({v for v in values if values.count(v) > 1})
        if shared:
            raise ValueError(
                f"{scope} shared by more than one court in this sync: {shared}"
            )


def _upsert_sources(model, entries, *, natural: str) -> list[str]:
    """Upsert ``entries`` by key. A row whose key no entry claims (a
    changed id, or a keyless row migrated before keys existed or
    admin-created) is adopted by its ``natural`` field. Returns the keys
    written, in display order."""
    rows = list(model.objects.all())
    authored = {entry.id for entry in entries}
    by_key = {r.key: r for r in rows if r.key}
    unclaimed = {getattr(r, natural): r for r in rows if r.key not in authored}
    keys: list[str] = []
    for order, entry in enumerate(entries):
        row = (
            by_key.get(entry.id)
            or unclaimed.pop(getattr(entry, natural), None)
            or model()
        )
        _apply(row, entry, exclude={"id"})
        row.key = entry.id
        row.order = order
        row.save()
        keys.append(entry.id)
    return keys


def _sync_contacts(courts: list[CourtSchema], *, strict: bool) -> None:
    """Upsert every court's contacts and resources by key."""
    _reject_shared_names(courts)
    _warn_removed_keys(
        "court contacts and resources",
        [
            *Contact.objects.values_list("key", flat=True),
            *Resource.objects.values_list("key", flat=True),
        ],
        [i for schema in courts for i in schema.source_ids],
    )
    contact_keys = _upsert_sources(
        Contact, [c for s in courts for c in s.contacts], natural="name"
    )
    resource_keys = _upsert_sources(
        Resource, [r for s in courts for r in s.resources], natural="label"
    )
    if strict:
        Contact.objects.exclude(key__in=contact_keys).delete()
        Resource.objects.exclude(key__in=resource_keys).delete()


def _sync_flow(
    topic: Topic,
    slug: str,
    schema: FlowSchema,
    forms: dict[str, Form],
    variables: dict[str, Variable],
) -> None:
    """Upsert one flow by (topic, slug) and replace its composition rows
    wholesale."""
    flow = topic.flows.filter(slug=slug).first() or TopicFlow(
        topic=topic, slug=slug
    )
    _apply(
        flow,
        schema,
        exclude={"sections", "interview", "packet", "deadlines", "links"},
    )
    flow.save()
    _warn_removed_keys(
        f"flow {topic.slug}/{slug}",
        [
            key
            for rows in (flow.sections, flow.deadlines, flow.links)
            for key in rows.values_list("key", flat=True)
        ],
        [
            source.id
            for source in (*schema.sections, *schema.deadlines, *schema.links)
        ],
    )
    flow.sections.all().delete()
    TopicFlowSection.objects.bulk_create(
        TopicFlowSection(**_source_row(row, flow=flow, order=order))
        for order, row in enumerate(schema.sections)
    )
    flow.interview_pages.all().delete()
    for order, page in enumerate(schema.interview):
        row = TopicFlowInterviewPage.objects.create(
            flow=flow, order=order, **page.model_dump(exclude={"variables"})
        )
        TopicFlowInterviewVariable.objects.bulk_create(
            TopicFlowInterviewVariable(
                page=row, variable=variables[name], order=position
            )
            for position, name in enumerate(page.variables)
        )
    flow.form_conditions.all().delete()
    for order, entry in enumerate(schema.packet):
        when = entry.when
        TopicFlowFormCondition.objects.create(
            flow=flow,
            form=forms[entry.form],
            variable=variables[when.variable] if when else None,
            operator=(
                when.operator
                if when
                else TopicFlowFormConditionOperator.EQUALS
            ),
            value=when.value if when else None,
            order=order,
        )
    flow.deadlines.all().delete()
    TopicFlowDeadline.objects.bulk_create(
        TopicFlowDeadline(
            **_source_row(
                row,
                flow=flow,
                order=order,
                offset_from=variables[row.offset_from],
            )
        )
        for order, row in enumerate(schema.deadlines)
    )
    flow.links.all().delete()
    TopicFlowLink.objects.bulk_create(
        TopicFlowLink(**_source_row(row, flow=flow, order=order))
        for order, row in enumerate(schema.links)
    )


@busts_cache(
    SITE_CACHE_KEY,
    TOPIC_LIST_CACHE_KEY,
    CONTACT_LIST_CACHE_KEY,
    RESOURCE_LIST_CACHE_KEY,
)
def corpus_sync(
    *, court: str | None = None, strict: bool = False
) -> dict[str, int]:
    """Upsert the corpus into the database by natural keys."""
    corpus = corpus_load()
    if court is None:
        court = settings.CORPUS_COURT
    if court is not None and court not in corpus.courts:
        raise ValueError(
            f"unknown court {court!r}; corpus has {sorted(corpus.courts)}"
        )
    deleted = 0
    with transaction.atomic():
        variables = _sync_variables(corpus)
        forms = _sync_forms(corpus, variables)
        topics: dict[str, Topic] = {}
        for (court_slug, topic_slug), schema in sorted(corpus.topics.items()):
            if court is not None and court_slug != court:
                continue
            topic = Topic.objects.filter(slug=topic_slug).first() or Topic(
                slug=topic_slug
            )
            _apply(topic, schema)
            topic.save()
            topics[topic_slug] = topic
        flow_count = 0
        flow_slugs: dict[str, list[str]] = {}
        for (court_slug, topic_slug, flow_slug), schema in sorted(
            corpus.flows.items()
        ):
            if court is not None and court_slug != court:
                continue
            _sync_flow(topics[topic_slug], flow_slug, schema, forms, variables)
            flow_slugs.setdefault(topic_slug, []).append(flow_slug)
            flow_count += 1
        if court is not None:
            _sync_site(court, corpus.courts[court])
        in_scope = [court] if court is not None else sorted(corpus.courts)
        _sync_contacts(
            [corpus.courts[slug] for slug in in_scope], strict=strict
        )
        if strict:
            for topic_slug, topic in topics.items():
                deleted += topic.flows.exclude(
                    slug__in=flow_slugs.get(topic_slug, [])
                ).delete()[0]
            deleted += Topic.objects.exclude(slug__in=topics).delete()[0]
            stale_forms = Form.objects.exclude(slug__in=corpus.forms)
            for form in stale_forms:
                form.file.delete(save=False)
            deleted += stale_forms.delete()[0]
        orphaned = Variable.objects.exclude(name__in=corpus.variables).update(
            in_schema=False
        )
    return {
        "variables": len(corpus.variables),
        "forms": len(corpus.forms),
        "topics": len(topics),
        "flows": flow_count,
        "deleted": deleted,
        "orphaned": orphaned,
    }
