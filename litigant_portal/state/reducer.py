from typing import assert_never

from litigant_portal.state.types import (
    ActionType,
    ConfirmFactsActionType,
    FactType,
    MarkViewedActionType,
    SetFactsActionType,
    StateType,
)


def reduce(current_state: StateType, action: ActionType) -> StateType:
    """
    Apply a validated action without I/O or mutation of its inputs.

    The caller establishes identity, checks the variable schema, and
    supplies actor authority. Timestamps come from the caller, never the
    reducer's clock.
    """
    next_state = current_state.model_copy(deep=True)
    match action:
        case SetFactsActionType():
            for name, incoming in action.facts.items():
                previous = next_state.facts.get(name)
                evidence = incoming.evidence
                if (
                    incoming.value is None
                    or not evidence
                    or not evidence.get("quote")
                ):
                    evidence = None
                if previous is not None and previous.value == incoming.value:
                    fact = FactType(
                        value=previous.value,
                        reviewed=previous.reviewed or action.actor == "human",
                        evidence=(
                            previous.evidence
                            if previous.evidence is not None
                            else evidence
                        ),
                        updated_at=previous.updated_at,
                    )
                else:
                    fact = FactType(
                        value=incoming.value,
                        reviewed=action.actor == "human",
                        evidence=evidence,
                        updated_at=action.at,
                    )
                next_state.facts[name] = fact.model_copy(deep=True)
        case ConfirmFactsActionType():
            for name in action.names:
                previous = next_state.facts.get(name)
                if (
                    previous is not None
                    and previous.value is not None
                    and not previous.reviewed
                    and previous.updated_at <= action.as_of
                ):
                    next_state.facts[name] = previous.model_copy(
                        update={"reviewed": True}
                    )
        case MarkViewedActionType():
            if current_state.flow_id is None:
                raise ValueError("Viewing a component requires a flow.")
            next_state.viewed[action.component_id] = action.signature
        case _:
            assert_never(action)
    return next_state
