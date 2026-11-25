import json
from collections.abc import Iterable

from django.forms.models import model_to_dict

from litigant_portal.app.models import (
    Contact,
    Resource,
    TopicFlow,
    UserIdentity,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.services.docassemble import interview_launch_url
from litigant_portal.app.topic_flow.contacts import contact_dicts
from litigant_portal.app.topic_flow.resources import resource_dicts
from litigant_portal.state.rules import parse_condition
from litigant_portal.state.types import (
    CalendarRuleType,
    ComponentRuleType,
    CourtRulesType,
    DeadlineRuleType,
    FactType,
    InformationRuleType,
    PacketEntryRuleType,
    PacketRuleType,
    QuestionsRuleType,
    StateType,
    VariableRuleType,
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
    from litigant_portal.app.topic_flow.rows import (
        flow_layout,
        section_anchor,
    )

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
                        id=f"interview-{number}",
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
            content = contact_dicts(contacts, id_attr="ref")
            if content:
                components.append(
                    InformationRuleType(id=key, content=json.dumps(content))
                )
        elif key == "resources":
            content = resource_dicts(resources, id_attr="ref")
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
