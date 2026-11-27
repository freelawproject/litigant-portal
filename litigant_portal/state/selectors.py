import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from django.forms.models import model_to_dict
from django.utils import timezone

from litigant_portal.app.models import Contact, Resource, UserIdentity
from litigant_portal.app.services.docassemble import interview_launch_url
from litigant_portal.state.models import (
    FlowViewState,
    TopicFlow,
    TopicFlowInterviewPage,
    TopicFlowSection,
    Variable,
    VariableAnswer,
)
from litigant_portal.state.projector import project
from litigant_portal.state.rules import default_layout, parse_condition
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
