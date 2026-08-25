"""Tests for the variable answer services.

variable_value_validate tests are DB-free and run in the fast suite;
the variable_answer_set tests are postgres-marked.
"""

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from litigant_portal.app.models import UserIdentity, Variable, VariableAnswer
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.services.topic_flow import (
    variable_answer_set,
    variable_value_validate,
)

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


@pytest.mark.postgres
class VariableAnswerSetTests(TestCase):
    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="abc123")
        self.variable = Variable.objects.create(
            name="favorite_county", data_type=VariableDataType.TEXT
        )

    def test_creates_answer_with_reviewed_false_by_default(self):
        answer = variable_answer_set(
            identity=self.identity, variable=self.variable, value="Cass"
        )
        self.assertEqual(answer.value, "Cass")
        self.assertFalse(answer.reviewed)

    def test_upsert_updates_existing_row_instead_of_duplicating(self):
        variable_answer_set(
            identity=self.identity, variable=self.variable, value="Cass"
        )
        variable_answer_set(
            identity=self.identity, variable=self.variable, value="Burleigh"
        )
        answers = VariableAnswer.objects.filter(
            identity=self.identity, variable=self.variable
        )
        self.assertEqual(answers.count(), 1)
        self.assertEqual(answers.get().value, "Burleigh")

    def test_invalid_value_raises_and_writes_nothing(self):
        with self.assertRaises(ValidationError):
            variable_answer_set(
                identity=self.identity, variable=self.variable, value=42
            )
        self.assertFalse(
            VariableAnswer.objects.filter(
                identity=self.identity, variable=self.variable
            ).exists()
        )

    def test_invalid_value_does_not_overwrite_existing_answer(self):
        variable_answer_set(
            identity=self.identity, variable=self.variable, value="Cass"
        )
        with self.assertRaises(ValidationError):
            variable_answer_set(
                identity=self.identity, variable=self.variable, value=42
            )
        answer = VariableAnswer.objects.get(
            identity=self.identity, variable=self.variable
        )
        self.assertEqual(answer.value, "Cass")

    def test_reviewed_true_when_explicitly_confirmed(self):
        answer = variable_answer_set(
            identity=self.identity,
            variable=self.variable,
            value="Cass",
            reviewed=True,
        )
        self.assertTrue(answer.reviewed)

    def test_new_value_resets_reviewed_to_false(self):
        # A human confirmed "Cass"; an unconfirmed rewrite to "Burleigh" must
        # not carry the old confirmation forward.
        variable_answer_set(
            identity=self.identity,
            variable=self.variable,
            value="Cass",
            reviewed=True,
        )
        answer = variable_answer_set(
            identity=self.identity, variable=self.variable, value="Burleigh"
        )
        self.assertFalse(answer.reviewed)

    def test_reconfirming_in_same_call_keeps_reviewed_true(self):
        variable_answer_set(
            identity=self.identity,
            variable=self.variable,
            value="Cass",
            reviewed=True,
        )
        answer = variable_answer_set(
            identity=self.identity,
            variable=self.variable,
            value="Burleigh",
            reviewed=True,
        )
        self.assertTrue(answer.reviewed)

    def test_unconfirmed_rewrite_of_same_value_resets_reviewed(self):
        # Deliberately conservative: an AI re-writing the value a human
        # already confirmed drops the confirmation, so the user re-confirms
        # rather than a stale confirmation reaching the prefill payload.
        variable_answer_set(
            identity=self.identity,
            variable=self.variable,
            value="Cass",
            reviewed=True,
        )
        answer = variable_answer_set(
            identity=self.identity, variable=self.variable, value="Cass"
        )
        self.assertFalse(answer.reviewed)
