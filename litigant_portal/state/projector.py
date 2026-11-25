import hashlib
import json
from collections.abc import Mapping
from datetime import date, timedelta
from typing import assert_never

from pydantic import JsonValue

from litigant_portal.state.rules import applicable_facts, condition_matches
from litigant_portal.state.types import (
    CalendarRuleType,
    CandidateType,
    ComponentProjectionType,
    ComponentRuleType,
    CourtRulesType,
    DeadlineProjectionType,
    DeadlineRuleType,
    InformationRuleType,
    PacketRuleType,
    ProjectionType,
    QuestionsRuleType,
    StateType,
    VariableRuleType,
)


def deadline_date(
    offset_days: int, source_name: str, answers: Mapping[str, JsonValue]
) -> date | None:
    """
    Resolve an offset from a stored ISO date, leaving unknown dates unset.
    """
    raw = answers.get(source_name)
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw) + timedelta(days=offset_days)
    except (ValueError, OverflowError):
        return None


def _deadline(
    rule: DeadlineRuleType, values: Mapping[str, JsonValue], today: date
) -> DeadlineProjectionType:
    due = deadline_date(rule.offset_days, rule.offset_from, values)
    return DeadlineProjectionType(
        id=rule.id, date=due, is_past=due is not None and due < today
    )


def _content_signature(
    component: ComponentRuleType,
    variables: Mapping[str, VariableRuleType],
    forms: tuple[str, ...],
    deadlines: tuple[DeadlineProjectionType, ...],
) -> str:
    contents = {
        "kind": component.kind,
        "content": component.content,
        "variables": [
            (name, rule.model_dump(mode="json", by_alias=True))
            for name, rule in variables.items()
        ],
        "forms": forms,
        "deadlines": [d.model_dump(mode="json") for d in deadlines],
        "interview_available": (
            isinstance(component, PacketRuleType)
            and component.interview_available
        ),
    }
    encoded = json.dumps(contents, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def project(
    state: StateType,
    court_rules: CourtRulesType,
    time_context: date,
    limit: int = 1,
) -> ProjectionType:
    """
    Derive progress and select unfinished components in authored order.

    The caller supplies validated court rules and the local calendar date.
    Component content is authored text, including question wording and
    choices. Its signature combines that text with the resolved contents.
    Viewing history belongs to this flow; it never confirms an answer.
    """
    if state.flow_id != court_rules.flow_id:
        raise ValueError("State and court rules must refer to the same flow.")
    if limit < 1:
        raise ValueError("Projection limit must be positive.")

    values = applicable_facts(
        {
            name: fact.value
            for name, fact in state.facts.items()
            if name in court_rules.variables
        },
        {
            name: rule.asked_when
            for name, rule in court_rules.variables.items()
        },
    )
    confirmed = {name for name in values if state.facts[name].reviewed}
    components = []
    names: list[str] = []
    forms: list[str] = []
    deadlines: list[DeadlineProjectionType] = []
    for component in court_rules.components:
        if not condition_matches(component.when, values):
            continue
        variables: tuple[str, ...] = ()
        selected_forms: tuple[str, ...] = ()
        resolved_deadlines: tuple[DeadlineProjectionType, ...] = ()
        match component:
            case QuestionsRuleType():
                variables = tuple(
                    name
                    for name in component.variables
                    if condition_matches(
                        court_rules.variables[name].asked_when, values
                    )
                )
                if not variables:
                    continue
            case PacketRuleType():
                selected_forms = tuple(
                    dict.fromkeys(
                        entry.form
                        for entry in component.entries
                        if condition_matches(entry.when, values)
                    )
                )
                if not selected_forms and not component.interview_available:
                    continue
            case CalendarRuleType():
                resolved_deadlines = tuple(
                    _deadline(rule, values, time_context)
                    for rule in component.deadlines
                    if condition_matches(rule.when, values)
                )
                if not resolved_deadlines:
                    continue
            case InformationRuleType():
                pass
            case _:
                assert_never(component)

        signature = _content_signature(
            component,
            {name: court_rules.variables[name] for name in variables},
            selected_forms,
            resolved_deadlines,
        )
        complete = state.viewed.get(component.id) == signature
        if isinstance(component, QuestionsRuleType):
            required = {
                name
                for name in variables
                if court_rules.variables[name].required
            }
            complete = required <= confirmed and (
                complete or set(variables) <= confirmed
            )
        components.append(
            ComponentProjectionType(
                id=component.id,
                signature=signature,
                complete=complete,
                variables=variables,
            )
        )
        names.extend(variables)
        forms.extend(selected_forms)
        deadlines.extend(resolved_deadlines)

    ordered_names = tuple(dict.fromkeys(names))
    return ProjectionType(
        flow_id=court_rules.flow_id,
        as_of=time_context,
        applicable_variables=ordered_names,
        answered=tuple(name for name in ordered_names if name in values),
        missing_required=tuple(
            name
            for name in ordered_names
            if court_rules.variables[name].required and name not in values
        ),
        unconfirmed=tuple(
            name
            for name in ordered_names
            if name in values and name not in confirmed
        ),
        components=tuple(components),
        candidates=tuple(
            CandidateType(component_id=c.id)
            for c in components
            if not c.complete
        )[:limit],
        forms=tuple(dict.fromkeys(forms)),
        deadlines=tuple(deadlines),
    )
