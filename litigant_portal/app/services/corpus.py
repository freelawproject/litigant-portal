from __future__ import annotations

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models.deletion import ProtectedError

from litigant_portal.app.cache import SITE_CACHE_KEY, TOPIC_LIST_CACHE_KEY
from litigant_portal.app.models import (
    Contact,
    Court,
    CourtTopic,
    Form,
    FormField,
    ImportAudit,
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
    FORMS_DIR,
    CorpusSchema,
    CourtSchema,
    FlowSchema,
    corpus_load,
)
from litigant_portal.app.selectors.site import site_get

from .utils import busts_cache


def _apply(row, schema, *, exclude: set[str] = frozenset()) -> None:
    """Set each schema field onto the row. ``exclude`` names the fields
    the caller resolves itself (relations, files, display-only)."""
    for field, value in schema.model_dump(exclude=exclude).items():
        setattr(row, field, value)


def _sync_variables(corpus: CorpusSchema) -> dict[str, Variable]:
    """
    Resolve gate references and append changed variable definitions.
    """
    rows = {}

    def resolve(name):
        if name in rows:
            return rows[name]
        schema = corpus.variables[name]
        gate = schema.asked_when
        validation = {
            "type": {"boolean": "boolean", "number": "number"}.get(
                schema.data_type, "string"
            )
        }
        if schema.data_type == "choice":
            validation["enum"] = [choice.value for choice in schema.choices]
        values = schema.model_dump(exclude={"asked_when"})
        values.update(
            value_schema=validation,
            in_schema=True,
            asked_when_id=resolve(gate.variable).id if gate else None,
            asked_when_value=gate.value if gate else None,
        )
        previous = (
            Variable.objects.filter(name=name).order_by("-version").first()
        )
        if previous and all(
            getattr(previous, key) == value for key, value in values.items()
        ):
            rows[name] = previous
        else:
            rows[name] = Variable.objects.create(
                **values, version=previous.version + 1 if previous else 1
            )
        return rows[name]

    for name in corpus.variables:
        resolve(name)
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


def _sync_forms(
    corpus: CorpusSchema, variables: dict[str, Variable]
) -> dict[str, Form]:
    """Upsert every form by slug, rewriting its stored PDF and replacing
    its field mappings wholesale."""
    rows = {f.slug: f for f in Form.objects.all()}
    for slug, schema in corpus.forms.items():
        form = rows.get(slug) or Form(slug=slug)
        _apply(form, schema, exclude={"fields"})
        if form.file:
            form.file.delete(save=False)
        # Also clear the target name: a stray file there (an orphan from a
        # prior sync) would otherwise suffix the new name on every sync.
        target = f"forms/{slug}.pdf"
        if form.file.storage.exists(target):
            form.file.storage.delete(target)
        form.file.save(
            f"{slug}.pdf",
            ContentFile((FORMS_DIR / f"{slug}.pdf").read_bytes()),
            save=False,
        )
        form.save()
        form.fields.all().delete()
        FormField.objects.bulk_create(
            _form_field(form, order, mapping, variables)
            for order, mapping in enumerate(schema.fields)
        )
        rows[slug] = form
    return rows


def _sync_site(court) -> None:
    """
    Point the site's existing court interface at the shared court record.
    """
    site = site_get()
    site.court = court
    site.save(update_fields=["court", "updated_at"])


def _sync_contacts(courts: list[CourtSchema], *, strict: bool) -> None:
    """Upsert every court's contacts and resources by name and label."""
    contacts = {c.name: c for c in Contact.objects.all()}
    resources = {r.label: r for r in Resource.objects.all()}
    names: list[str] = []
    labels: list[str] = []
    for schema in courts:
        for entry in schema.contacts:
            row = contacts.get(entry.name) or Contact(name=entry.name)
            _apply(row, entry)
            row.order = len(names)
            row.save()
            contacts[entry.name] = row
            names.append(entry.name)
        for entry in schema.resources:
            row = resources.get(entry.label) or Resource(label=entry.label)
            _apply(row, entry)
            row.order = len(labels)
            row.save()
            resources[entry.label] = row
            labels.append(entry.label)
    if strict:
        Contact.objects.exclude(name__in=names).delete()
        Resource.objects.exclude(label__in=labels).delete()


def _sync_flow(
    topic: Topic,
    slug: str,
    schema: FlowSchema,
    forms: dict[str, Form],
    variables: dict[str, Variable],
    court_topic,
    audit,
) -> None:
    """
    Refresh a court/topic flow and replace its existing composition rows.
    """
    flow = topic.flows.filter(court_topic=court_topic, slug=slug).order_by(
        "-version"
    ).first() or TopicFlow(
        topic=topic, court_topic=court_topic, slug=slug, import_audit=audit
    )
    _apply(
        flow,
        schema,
        exclude={"sections", "interview", "packet", "deadlines", "links"},
    )
    flow.save()
    flow.sections.all().delete()
    TopicFlowSection.objects.bulk_create(
        TopicFlowSection(flow=flow, order=order, **row.model_dump())
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
            flow=flow,
            order=order,
            offset_from=variables[row.offset_from],
            **row.model_dump(exclude={"offset_from"}),
        )
        for order, row in enumerate(schema.deadlines)
    )
    flow.links.all().delete()
    TopicFlowLink.objects.bulk_create(
        TopicFlowLink(flow=flow, order=order, **row.model_dump())
        for order, row in enumerate(schema.links)
    )


@busts_cache(SITE_CACHE_KEY, TOPIC_LIST_CACHE_KEY)
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
        audit = ImportAudit.objects.create(
            invocation_type="corpus_sync", code_version=settings.GIT_SHA
        )
        courts = {}
        for slug, schema in corpus.courts.items():
            if court is not None and slug != court:
                continue
            row, _ = Court.objects.get_or_create(
                slug=slug, defaults={"name": schema.name}
            )
            _apply(row, schema, exclude={"contacts", "resources"})
            row.save()
            courts[slug] = row
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
            pair, _ = CourtTopic.objects.get_or_create(
                court=courts[court_slug], topic=topics[topic_slug]
            )
            _sync_flow(
                topics[topic_slug],
                flow_slug,
                schema,
                forms,
                variables,
                pair,
                audit,
            )
            flow_slugs.setdefault(topic_slug, []).append(flow_slug)
            flow_count += 1
        if court is not None:
            _sync_site(courts[court])
        in_scope = [court] if court is not None else sorted(corpus.courts)
        _sync_contacts(
            [corpus.courts[slug] for slug in in_scope], strict=strict
        )
        if strict:
            for topic_slug, topic in topics.items():
                deleted += topic.flows.exclude(
                    slug__in=flow_slugs.get(topic_slug, [])
                ).delete()[0]
            for stale in Topic.objects.exclude(slug__in=topics):
                try:
                    with transaction.atomic():
                        deleted += stale.flows.filter(state="draft").delete()[
                            0
                        ]
                        CourtTopic.objects.filter(topic=stale).delete()
                        deleted += stale.delete()[0]
                except ProtectedError:
                    CourtTopic.objects.filter(topic=stale).update(
                        enabled=False
                    )
                    Topic.objects.filter(pk=stale.pk).update(enabled=False)
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
