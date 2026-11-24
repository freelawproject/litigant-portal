import pytest
from pydantic import TypeAdapter, ValidationError

from litigant_portal.app.models.choices import TopicFlowFormConditionOperator
from litigant_portal.app.models.topic_flow import condition_holds
from litigant_portal.state.rules import ConditionType, condition_matches


def test_unanswered_fact_does_not_satisfy_a_negated_condition():
    assert not condition_holds(
        {}, "county", "Cass", TopicFlowFormConditionOperator.NOT_EQUALS
    )


@pytest.mark.parametrize(
    ("condition", "facts", "expected"),
    [
        ({"not": {"fact": "gate", "equals": True}}, {}, False),
        ({"not": {"fact": "gate", "equals": True}}, {"gate": None}, False),
        ({"not": {"fact": "gate", "equals": True}}, {"gate": False}, True),
        (
            {
                "all": [
                    {"fact": "gate", "equals": True},
                    {"not": {"fact": "other", "equals": True}},
                ]
            },
            {"gate": True},
            False,
        ),
        (
            {
                "any": [
                    {"fact": "gate", "equals": True},
                    {"fact": "other", "equals": True},
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
    [{"all": []}, {"fact": "gate", "equals": True, "extra": True}],
)
def test_invalid_conditions_are_rejected(condition):
    with pytest.raises(ValidationError):
        TypeAdapter(ConditionType).validate_python(condition)
