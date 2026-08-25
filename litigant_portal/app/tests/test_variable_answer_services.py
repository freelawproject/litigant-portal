"""Fast, DB-free tests: variable_value_validate returns valid values unchanged (None always passes) and raises ValidationError otherwise."""

import pytest
from django.core.exceptions import ValidationError

from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.services.topic_flow import variable_value_validate

# Variable.choices is stored as the corpus writes it: {value, label} dicts.
COUNTY_CHOICES = [
    {"value": "cass", "label": "Cass County"},
    {"value": "burleigh", "label": "Burleigh County"},
]


@pytest.mark.parametrize(
    ("data_type", "choices", "value"),
    [
        (VariableDataType.TEXT, [], None),
        (VariableDataType.TEXT, [], "Cass"),
        (VariableDataType.NUMBER, [], 3),
        (VariableDataType.NUMBER, [], 3.5),
        (VariableDataType.BOOLEAN, [], True),
        (VariableDataType.BOOLEAN, [], False),
        (VariableDataType.DATE, [], "2026-02-01"),
        (VariableDataType.DATETIME, [], "2026-02-01T10:30:00"),
        (VariableDataType.CHOICE, COUNTY_CHOICES, "cass"),
    ],
    ids=[
        "none-always-passes",
        "text-accepts-string",
        "number-accepts-int",
        "number-accepts-float",
        "boolean-accepts-true",
        "boolean-accepts-false",
        "date-accepts-iso-string",
        "datetime-accepts-iso-string",
        "choice-accepts-declared-value",
    ],
)
def test_valid_values_pass_unchanged(data_type, choices, value):
    assert (
        variable_value_validate(
            data_type=data_type, choices=choices, value=value
        )
        == value
    )


@pytest.mark.parametrize(
    ("data_type", "choices", "value"),
    [
        (VariableDataType.TEXT, [], 42),
        (VariableDataType.NUMBER, [], True),
        (VariableDataType.NUMBER, [], "3"),
        (VariableDataType.BOOLEAN, [], "true"),
        (VariableDataType.DATE, [], "not-a-date"),
        (VariableDataType.DATETIME, [], "not-a-datetime"),
        (VariableDataType.CHOICE, COUNTY_CHOICES, "stark"),
        (VariableDataType.CHOICE, COUNTY_CHOICES, "Cass County"),
    ],
    ids=[
        "text-rejects-non-string",
        "number-rejects-bool",
        "number-rejects-numeric-string",
        "boolean-rejects-non-bool",
        "date-rejects-unparseable-string",
        "datetime-rejects-unparseable-string",
        "choice-rejects-undeclared-value",
        "choice-rejects-label-instead-of-value",
    ],
)
def test_invalid_values_raise(data_type, choices, value):
    with pytest.raises(ValidationError):
        variable_value_validate(
            data_type=data_type, choices=choices, value=value
        )
