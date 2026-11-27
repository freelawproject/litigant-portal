"""
Stored answer selection preserves identity ownership and glossary membership.
"""

import pytest
from django.test import TestCase

from litigant_portal.app.models import UserIdentity, Variable, VariableAnswer
from litigant_portal.state.models import VariableDataType
from litigant_portal.state.selectors import variable_answer_list


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

    def test_omits_answers_to_out_of_schema_variables(self):
        # sync_corpus keeps the row so a migration can move the answer, but
        # nothing references the variable anymore.
        vestigial = Variable.objects.create(
            name="old_county",
            data_type=VariableDataType.TEXT,
            in_schema=False,
        )
        VariableAnswer.objects.create(
            identity=self.identity, variable=vestigial, value="Stark"
        )
        VariableAnswer.objects.create(
            identity=self.identity, variable=self.county, value="Cass"
        )
        answers = variable_answer_list(identity=self.identity)
        self.assertEqual(
            [a.variable.name for a in answers], ["residence_county"]
        )
