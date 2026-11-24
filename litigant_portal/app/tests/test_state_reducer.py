from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from litigant_portal.state.reducer import reduce
from litigant_portal.state.types import (
    ActionType,
    ConfirmFactsActionType,
    FactInputType,
    FactType,
    MarkViewedActionType,
    SetFactsActionType,
    StateType,
)

NOW = datetime(2026, 11, 24, tzinfo=UTC)
BEFORE = NOW - timedelta(minutes=1)


def test_batch_reduction_preserves_unrelated_state_and_input_ownership():
    state = StateType(
        identity_id=1,
        flow_id=uuid4(),
        viewed={"overview": "a" * 64},
        facts={
            "county": FactType(value="Cass", reviewed=True, updated_at=BEFORE),
            "name": FactType(value="Sandra", reviewed=True, updated_at=BEFORE),
        },
    )
    action = SetFactsActionType(
        actor="assistant",
        at=NOW,
        facts={
            "county": FactInputType(
                value="Burleigh", evidence={"quote": "I moved to Burleigh."}
            ),
            "name": FactInputType(value=None),
        },
    )

    result = reduce(state, action)

    assert result.facts["county"].value == "Burleigh"
    assert result.facts["county"].reviewed is False
    assert result.facts["county"].updated_at == NOW
    assert result.facts["name"].value is None
    assert result.facts["name"].reviewed is False
    assert result.viewed == state.viewed
    result.viewed.clear()
    result.facts["county"].evidence["quote"] = "Changed outside the reducer."
    assert state.viewed == {"overview": "a" * 64}
    assert state.facts["county"].value == "Cass"
    assert state.facts["name"].value == "Sandra"
    assert action.facts["county"].evidence == {"quote": "I moved to Burleigh."}


def test_confirmation_only_accepts_values_visible_at_the_review_time():
    state = StateType(
        identity_id=1,
        facts={
            "name": FactType(value="Sandra", updated_at=BEFORE),
            "county": FactType(value="Cass", updated_at=NOW),
            "cleared": FactType(value=None, updated_at=BEFORE),
        },
    )
    result = reduce(
        state,
        ConfirmFactsActionType(
            actor="human",
            names=("name", "county", "cleared", "unknown"),
            as_of=BEFORE,
        ),
    )

    assert result.facts["name"].reviewed is True
    assert result.facts["name"].updated_at == BEFORE
    assert result.facts["county"].reviewed is False
    assert result.facts["cleared"].reviewed is False
    assert "unknown" not in result.facts
    assert state.facts["name"].reviewed is False


def test_viewing_a_section_updates_only_the_scoped_viewing_state():
    action = MarkViewedActionType(
        actor="human", component_id="overview", signature="a" * 64
    )
    with pytest.raises(ValueError, match="requires a flow"):
        reduce(StateType(identity_id=1), action)

    state = StateType(identity_id=1, flow_id=uuid4())
    result = reduce(state, action)

    assert result.viewed == {"overview": "a" * 64}
    assert result.facts == state.facts
    assert state.viewed == {}


def test_an_assistant_cannot_supply_a_confirmation_action():
    with pytest.raises(ValidationError):
        TypeAdapter(ActionType).validate_python(
            {
                "kind": "confirm_facts",
                "actor": "assistant",
                "names": ("county",),
                "as_of": NOW,
            }
        )
