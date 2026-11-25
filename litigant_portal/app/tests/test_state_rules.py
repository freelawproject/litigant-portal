import pytest
from pydantic import TypeAdapter, ValidationError

from litigant_portal.state.rules import (
    applicable_facts,
    condition_matches,
    parse_condition,
)
from litigant_portal.state.types import ConditionType


@pytest.mark.parametrize(
    ("condition", "facts", "expected"),
    [
        ({"not": {"variable": "gate", "value": True}}, {}, False),
        ({"not": {"variable": "gate", "value": True}}, {"gate": None}, False),
        ({"not": {"variable": "gate", "value": True}}, {"gate": False}, True),
        (
            {"variable": "gate", "value": True, "operator": "not_equals"},
            {},
            False,
        ),
        (
            {"variable": "gate", "value": True, "operator": "not_equals"},
            {"gate": False},
            True,
        ),
        (
            {
                "all": [
                    {"variable": "gate", "value": True},
                    {"not": {"variable": "other", "value": True}},
                ]
            },
            {"gate": True},
            False,
        ),
        (
            {
                "any": [
                    {"variable": "gate", "value": True},
                    {"variable": "other", "value": True},
                ]
            },
            {"gate": True},
            True,
        ),
    ],
)
def test_compound_conditions_preserve_unknown_prerequisites(
    condition, facts, expected
):
    parsed = TypeAdapter(ConditionType).validate_python(condition)
    assert condition_matches(parsed, facts) is expected


@pytest.mark.parametrize(
    "condition",
    [
        {"all": []},
        {"variable": "gate"},
        {"variable": "gate", "value": True, "extra": True},
    ],
)
def test_invalid_conditions_are_rejected(condition):
    with pytest.raises(ValidationError):
        TypeAdapter(ConditionType).validate_python(condition)


@pytest.mark.parametrize("gate", [None, False, True])
def test_hidden_prerequisites_stay_unknown_until_their_path_applies(gate):
    facts = {"gate": gate, "detail": True, "dependent": "kept"}
    conditions = {
        "dependent": parse_condition(
            {"not": {"variable": "detail", "value": False}}
        ),
        "detail": parse_condition({"variable": "gate", "value": True}),
        "gate": None,
    }
    projected = applicable_facts(facts, conditions)
    if gate is True:
        assert projected == facts
    else:
        assert projected == ({} if gate is None else {"gate": False})
    assert facts["detail"] is True
    assert facts["dependent"] == "kept"
