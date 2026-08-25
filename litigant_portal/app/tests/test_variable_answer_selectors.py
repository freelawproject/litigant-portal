"""Postgres tests: variable_answer_list/variable_answer_map read an identity's answers scoped to that identity and to the requested names."""

import pytest
from django.test import TestCase

from litigant_portal.app.models import UserIdentity, Variable, VariableAnswer
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.selectors.topic_flow import (
    variable_answer_list,
    variable_answer_map,
)


@pytest.mark.postgres
class VariableAnswerListTests(TestCase):
    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="abc123")
        self.other_identity = UserIdentity.objects.create(session_key="xyz789")
        self.county = Variable.objects.create(
            name="residence_county", data_type=VariableDataType.TEXT
        )
        self.city = Variable.objects.create(
            name="residence_city", data_type=VariableDataType.TEXT
        )

    def test_returns_only_this_identitys_answers(self):
        VariableAnswer.objects.create(
            identity=self.identity, variable=self.county, value="Cass"
        )
        VariableAnswer.objects.create(
            identity=self.other_identity, variable=self.city, value="Fargo"
        )
        answers = variable_answer_list(identity=self.identity)
        self.assertEqual(
            [a.variable.name for a in answers], ["residence_county"]
        )

    def test_returns_empty_list_when_no_answers(self):
        self.assertEqual(variable_answer_list(identity=self.identity), [])

    def test_ordered_by_variable_name(self):
        VariableAnswer.objects.create(
            identity=self.identity, variable=self.county, value="Cass"
        )
        VariableAnswer.objects.create(
            identity=self.identity, variable=self.city, value="Fargo"
        )
        answers = variable_answer_list(identity=self.identity)
        self.assertEqual(
            [a.variable.name for a in answers],
            ["residence_city", "residence_county"],
        )


@pytest.mark.postgres
class VariableAnswerMapTests(TestCase):
    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="abc123")
        self.other_identity = UserIdentity.objects.create(session_key="xyz789")
        self.county = Variable.objects.create(
            name="residence_county", data_type=VariableDataType.TEXT
        )
        self.city = Variable.objects.create(
            name="residence_city", data_type=VariableDataType.TEXT
        )

    def test_maps_requested_names_to_values(self):
        VariableAnswer.objects.create(
            identity=self.identity, variable=self.county, value="Cass"
        )
        VariableAnswer.objects.create(
            identity=self.identity, variable=self.city, value="Fargo"
        )
        result = variable_answer_map(
            identity=self.identity,
            names=["residence_county", "residence_city"],
        )
        self.assertEqual(
            result, {"residence_county": "Cass", "residence_city": "Fargo"}
        )

    def test_omits_names_with_no_answer(self):
        VariableAnswer.objects.create(
            identity=self.identity, variable=self.county, value="Cass"
        )
        result = variable_answer_map(
            identity=self.identity,
            names=["residence_county", "residence_city"],
        )
        self.assertEqual(result, {"residence_county": "Cass"})

    def test_omits_names_not_requested(self):
        VariableAnswer.objects.create(
            identity=self.identity, variable=self.county, value="Cass"
        )
        VariableAnswer.objects.create(
            identity=self.identity, variable=self.city, value="Fargo"
        )
        result = variable_answer_map(
            identity=self.identity, names=["residence_county"]
        )
        self.assertEqual(result, {"residence_county": "Cass"})

    def test_scoped_to_this_identity_only(self):
        VariableAnswer.objects.create(
            identity=self.other_identity, variable=self.county, value="Cass"
        )
        result = variable_answer_map(
            identity=self.identity, names=["residence_county"]
        )
        self.assertEqual(result, {})
