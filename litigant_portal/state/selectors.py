import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from django.core.cache import cache
from django.forms.models import model_to_dict
from django.utils import timezone

from litigant_portal.app.cache import (
    TOPIC_FLOW_LIST_CACHE_KEY,
    TOPIC_LIST_CACHE_KEY,
)
from litigant_portal.app.models import Contact, Resource, UserIdentity
from litigant_portal.app.services.docassemble import interview_launch_url
from litigant_portal.state.models import (
    FlowViewState,
    Topic,
    TopicFlow,
    TopicFlowInterviewPage,
    TopicFlowSection,
    Variable,
    VariableAnswer,
)
from litigant_portal.state.projector import project
from litigant_portal.state.rules import (
    applicable_facts,
    default_layout,
    parse_condition,
)
from litigant_portal.state.types import (
    CalendarRuleType,
    ComponentRuleType,
    CourtRulesType,
    DeadlineRuleType,
    FactType,
    InformationRuleType,
    PacketEntryRuleType,
    PacketRuleType,
    ProjectionType,
    QuestionsRuleType,
    StateType,
    VariableRuleType,
)


@dataclass(frozen=True)
class FlowStateType:
    state: StateType
    projection: ProjectionType
    variables: dict[str, Variable]
    answers: dict[str, VariableAnswer]


def flow_state(
    *,
    identity: UserIdentity | None,
    flow: TopicFlow,
    contacts: Iterable[Contact],
    resources: Iterable[Resource],
    limit: int = 1,
    time_context: date | None = None,
) -> FlowStateType:
    """
    Load a fresh snapshot and compute one projection for the caller.

    Anonymous reads use an empty snapshot without creating an identity.
    Writes always resolve a real identity through the request middleware.
    """
    variables = {v.name: v for v in Variable.objects.filter(in_schema=True)}
    answers = {}
    if identity is None:
        state = StateType(identity_id=0, flow_id=flow.pk)
    else:
        answers = {
            answer.variable.name: answer
            for answer in VariableAnswer.objects.filter(
                identity=identity
            ).select_related("variable")
        }
        viewed = (
            FlowViewState.objects.filter(identity=identity, flow=flow)
            .values_list("viewed", flat=True)
            .first()
        )
        state = state_snapshot(
            identity=identity,
            flow=flow,
            answers=answers.values(),
            viewed=viewed,
        )
    rules = court_rules(
        flow=flow,
        variables=variables.values(),
        contacts=contacts,
        resources=resources,
    )
    return FlowStateType(
        state,
        project(state, rules, time_context or timezone.localdate(), limit),
        variables,
        answers,
    )


def state_snapshot(
    *,
    identity: UserIdentity,
    answers: Iterable[VariableAnswer],
    flow: TopicFlow | None = None,
    viewed: dict[str, str] | None = None,
) -> StateType:
    """
    Adapt already-loaded rows, preserving the caller's transaction scope.
    """
    return StateType(
        identity_id=identity.pk,
        flow_id=flow.pk if flow is not None else None,
        viewed=viewed if viewed is not None else {},
        facts={
            answer.variable.name: FactType(
                value=answer.value,
                reviewed=answer.reviewed,
                evidence=answer.evidence,
                updated_at=answer.updated_at,
            )
            for answer in answers
        },
    )


def section_anchor(section: TopicFlowSection, number: int) -> str:
    """
    Preserve positional anchors for older rows without an authored key.
    """
    return section.key or f"section-{number}"


def interview_anchor(number: int) -> str:
    """
    Identify a question group by its authored page position.
    """
    return f"interview-{number}"


def flow_layout(
    flow: TopicFlow, sections: Iterable[TopicFlowSection]
) -> list[str]:
    """
    Use authored order, falling back to sections followed by output blocks.
    """
    return list(flow.layout) or default_layout(
        section_anchor(section, number)
        for number, section in enumerate(sections, 1)
    )


def flow_pages(
    flow: TopicFlow,
) -> list[tuple[TopicFlowInterviewPage, list[Variable]]]:
    """
    Read question groups in their authored page and placement order.
    """
    return [
        (page, [placed.variable for placed in page.variables.all()])
        for page in flow.interview_pages.all()
    ]


def court_rules(
    *,
    flow: TopicFlow,
    variables: Iterable[Variable],
    contacts: Iterable[Contact],
    resources: Iterable[Resource],
) -> CourtRulesType:
    """
    Adapt the prefetched flow graph and glossary in authored layout order.

    Content contains authored wording and output metadata, never answers.
    Keeping it in the rules gives both projectors the same source material
    and invalidates viewed signatures when that material changes.
    """
    sections = list(flow.sections.all())
    by_key = {
        section_anchor(section, number): section
        for number, section in enumerate(sections, 1)
    }
    components: list[ComponentRuleType] = []
    for key in flow_layout(flow, sections):
        if key in by_key:
            section = by_key[key]
            components.append(
                InformationRuleType(
                    id=key,
                    content=f"{section.heading}\n\n{section.content}",
                    when=parse_condition(section.when),
                )
            )
        elif key == "interview":
            for number, page in enumerate(flow.interview_pages.all(), 1):
                placed = [p.variable for p in page.variables.all()]
                components.append(
                    QuestionsRuleType(
                        id=interview_anchor(number),
                        content=json.dumps(
                            {
                                "title": page.title,
                                "description": page.description,
                                "variables": [
                                    model_to_dict(
                                        variable,
                                        fields=(
                                            "name",
                                            "label",
                                            "question",
                                            "help_text",
                                            "data_type",
                                            "choices",
                                            "default",
                                            "is_private",
                                        ),
                                    )
                                    for variable in placed
                                ],
                            }
                        ),
                        when=parse_condition(page.when),
                        variables=tuple(v.name for v in placed),
                    )
                )
        elif key == "packet":
            entries = list(flow.form_conditions.all())
            components.append(
                PacketRuleType(
                    id=key,
                    content=json.dumps(
                        {
                            "forms": [
                                model_to_dict(
                                    e.form, fields=("slug", "name", "url")
                                )
                                for e in entries
                            ],
                            "interview": flow.interview_reference,
                        }
                    ),
                    entries=tuple(
                        PacketEntryRuleType(
                            form=e.form.slug, when=parse_condition(e.when)
                        )
                        for e in entries
                    ),
                    interview_available=bool(
                        flow.interview_reference
                        and interview_launch_url(flow.interview_reference)
                    ),
                )
            )
        elif key == "calendar":
            deadlines = list(flow.deadlines.all())
            components.append(
                CalendarRuleType(
                    id=key,
                    content=json.dumps(
                        [
                            model_to_dict(
                                d, fields=("key", "label", "description")
                            )
                            for d in deadlines
                        ]
                    ),
                    deadlines=tuple(
                        DeadlineRuleType(
                            id=d.ref,
                            offset_from=d.offset_from.name,
                            offset_days=d.offset_days,
                            when=parse_condition(d.when),
                        )
                        for d in deadlines
                    ),
                )
            )
        elif key == "contacts":
            content = [
                {
                    "id": contact.ref,
                    **model_to_dict(
                        contact,
                        fields=(
                            "name",
                            "phone",
                            "email",
                            "url",
                            "address",
                            "hours",
                            "note",
                        ),
                    ),
                }
                for contact in contacts
            ]
            if content:
                components.append(
                    InformationRuleType(id=key, content=json.dumps(content))
                )
        elif key == "resources":
            content = [
                {
                    "id": resource.ref,
                    **model_to_dict(resource, fields=("label", "url", "note")),
                }
                for resource in resources
            ]
            if content:
                components.append(
                    InformationRuleType(id=key, content=json.dumps(content))
                )
    return CourtRulesType(
        flow_id=flow.pk,
        variables={
            variable.name: VariableRuleType(
                required=variable.required, asked_when=variable.condition
            )
            for variable in variables
            if variable.in_schema
        },
        components=tuple(components),
    )


def topic_list() -> list[Topic]:
    """
    Topics in display order, served from cache.
    """
    topics = cache.get(TOPIC_LIST_CACHE_KEY)
    if topics is None:
        topics = list(Topic.objects.all())
        cache.set(TOPIC_LIST_CACHE_KEY, topics, timeout=None)
    return topics


def topic_court_find() -> str | None:
    """
    The one court every topic belongs to, or None when the topics span
    several courts or there are none (#886). Read from the rows, not the
    cache: ``sync_corpus`` calls it at startup, before anything is cached.
    A topic that predates its first sync has a blank court and is skipped.
    """
    courts = set(
        Topic.objects.exclude(court="")
        .values_list("court", flat=True)
        .distinct()
    )
    return courts.pop() if len(courts) == 1 else None


def topic_get(*, topic_id: UUID) -> Topic:
    """
    A single topic (raises Topic.DoesNotExist).
    """
    return Topic.objects.get(id=topic_id)


def topic_flow_list() -> list[TopicFlow]:
    """
    Enabled flows with their topics, in topic order then flow order,
    served from cache.
    """
    flows = cache.get(TOPIC_FLOW_LIST_CACHE_KEY)
    if flows is None:
        flows = list(
            TopicFlow.objects.filter(enabled=True)
            .select_related("topic")
            .order_by(
                "topic__order", "topic__created_at", "order", "created_at"
            )
        )
        cache.set(TOPIC_FLOW_LIST_CACHE_KEY, flows, timeout=None)
    return flows


def topic_flow_find(
    *,
    topic_slug: str,
    flow_slug: str,
    court: str | None = None,
    graph: bool = True,
) -> TopicFlow | None:
    """
    The enabled flow at (topic_slug, flow_slug), or None. With ``court``
    the topic must carry that court too, for the page URL's check. With
    ``graph`` its whole content graph is prefetched, for the page; without,
    only the row and its topic, for a caller that reads a field or one
    relation.
    """
    flows = TopicFlow.objects.filter(
        topic__slug=topic_slug, slug=flow_slug, enabled=True
    ).select_related("topic")
    if court is not None:
        flows = flows.filter(topic__court=court)
    if graph:
        flows = flows.prefetch_related(
            "sections",
            "links",
            "deadlines__offset_from",
            "form_conditions__form",
            "interview_pages__variables__variable",
        )
    return flows.first()


def variable_answer_list(
    *, identity: UserIdentity, answered_only: bool = False
) -> list[VariableAnswer]:
    """
    An identity's answers, ordered by variable name.

    Answers to variables the corpus no longer names (``in_schema=False``)
    are left out: sync keeps those rows so a migration can move them, but
    no form references them, so no surface should show them.

    Inapplicable answers stay stored but are excluded, including when a
    prerequisite is itself inapplicable. Conditions use the whole identity
    snapshot before callers narrow to a flow or confirmed answers.

    ``answered_only`` drops cleared answers (``value`` None).
    """
    answers = VariableAnswer.objects.filter(
        identity=identity, variable__in_schema=True
    )
    if answered_only:
        answers = answers.filter(value__isnull=False)
    answers = list(
        answers.select_related("variable").order_by("variable__name")
    )
    applicable = applicable_facts(
        {a.variable.name: a.value for a in answers},
        {a.variable.name: a.variable.condition for a in answers},
    )
    return [a for a in answers if a.variable.is_asked(applicable)]


def variable_public_ids(*, variable_ids: list[UUID]) -> set[UUID]:
    """
    Return IDs that are still in the corpus and marked public.
    """
    return set(
        Variable.objects.filter(
            pk__in=variable_ids, in_schema=True, is_private=False
        )
        .order_by()
        .values_list("pk", flat=True)
    )


def variable_answer_unreviewed_names(
    *, identity: UserIdentity, names: list[str]
) -> list[str]:
    """
    The given names whose answer no human has confirmed yet, sorted.

    Cleared and out-of-schema answers are not pending. Names with no
    answer at all are left out too.

    Include currently hidden answers named by an older card, so it cannot
    report successful confirmation of an answer the write boundary refused.
    """
    return sorted(
        VariableAnswer.objects.filter(
            identity=identity,
            variable__name__in=names,
            variable__in_schema=True,
            value__isnull=False,
            reviewed=False,
        ).values_list("variable__name", flat=True)
    )
