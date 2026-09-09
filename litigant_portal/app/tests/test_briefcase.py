"""The briefcase panel's grouping selector and its chat-page context.

The panel shows an identity's stored facts grouped for reading. Grouping is
derived from each answered variable's own interview placement, not from an
"active flow" — the chat page has no flow server-side, so a placement-driven
grouping is the only one available without a model change.
"""

import pytest
from django.test import TestCase
from django.urls import reverse

from litigant_portal.app.models import (
    Topic,
    TopicFlow,
    TopicFlowInterviewPage,
    TopicFlowInterviewVariable,
    UserIdentity,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.selectors.topic_flow import briefcase_groups


def _place(page, variable, order):
    return TopicFlowInterviewVariable.objects.create(
        page=page, variable=variable, order=order
    )


@pytest.mark.postgres
class BriefcaseGroupsTests(TestCase):
    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="s1")
        self.topic = Topic.objects.create(slug="eviction", order=0)
        self.flow = TopicFlow.objects.create(
            topic=self.topic, slug="tenant", order=0
        )
        self.about_you = TopicFlowInterviewPage.objects.create(
            flow=self.flow, title="About you", order=0
        )
        self.your_notice = TopicFlowInterviewPage.objects.create(
            flow=self.flow, title="Your notice", order=1
        )

    def _answer(self, name, value, label=""):
        variable = Variable.objects.create(name=name, label=label)
        VariableAnswer.objects.create(
            identity=self.identity, variable=variable, value=value
        )
        return variable

    def test_groups_follow_page_order_not_variable_name(self):
        # Alphabetically "received_date" precedes "tenant_name", so a flat
        # name-ordered list would invert these two groups. Page order wins.
        tenant_name = self._answer("tenant_name", "Jamie")
        received = self._answer("received_date", "2026-09-01")
        _place(self.about_you, tenant_name, 0)
        _place(self.your_notice, received, 0)

        groups = briefcase_groups(identity=self.identity)

        self.assertEqual(
            [g["title"] for g in groups], ["About you", "Your notice"]
        )

    def test_variables_within_a_group_follow_placement_order(self):
        last = self._answer("tenant_last", "Rivera")
        first = self._answer("tenant_first", "Jamie")
        # Placement order is deliberately the reverse of alphabetical.
        _place(self.about_you, first, 0)
        _place(self.about_you, last, 1)

        groups = briefcase_groups(identity=self.identity)

        self.assertEqual(
            [a.variable.name for a in groups[0]["answers"]],
            ["tenant_first", "tenant_last"],
        )

    def test_unplaced_answers_land_in_a_titleless_group_last(self):
        placed = self._answer("tenant_name", "Jamie")
        _place(self.about_you, placed, 0)
        self._answer("court_name", "Franklin County Municipal Court")

        groups = briefcase_groups(identity=self.identity)

        self.assertEqual(groups[-1]["title"], "")
        self.assertEqual(
            [a.variable.name for a in groups[-1]["answers"]], ["court_name"]
        )

    def test_no_titleless_group_when_every_answer_is_placed(self):
        placed = self._answer("tenant_name", "Jamie")
        _place(self.about_you, placed, 0)

        groups = briefcase_groups(identity=self.identity)

        self.assertEqual([g["title"] for g in groups], ["About you"])

    def test_cleared_answers_are_left_out(self):
        # A None value is a cleared answer, not a fact. Showing the label with
        # an empty value reads as "we know this and it's blank".
        kept = self._answer("tenant_name", "Jamie")
        cleared = self._answer("hearing_date", None)
        _place(self.about_you, kept, 0)
        _place(self.about_you, cleared, 1)

        groups = briefcase_groups(identity=self.identity)

        self.assertEqual(
            [a.variable.name for a in groups[0]["answers"]], ["tenant_name"]
        )

    def test_out_of_schema_answers_are_left_out(self):
        kept = self._answer("tenant_name", "Jamie")
        _place(self.about_you, kept, 0)
        stale = Variable.objects.create(name="old_field", in_schema=False)
        VariableAnswer.objects.create(
            identity=self.identity, variable=stale, value="x"
        )
        _place(self.about_you, stale, 1)

        groups = briefcase_groups(identity=self.identity)

        self.assertEqual(
            [a.variable.name for a in groups[0]["answers"]], ["tenant_name"]
        )

    def test_another_identitys_answers_are_not_visible(self):
        other = UserIdentity.objects.create(session_key="s2")
        theirs = Variable.objects.create(name="tenant_name")
        VariableAnswer.objects.create(
            identity=other, variable=theirs, value="Someone else"
        )
        _place(self.about_you, theirs, 0)

        self.assertEqual(briefcase_groups(identity=self.identity), [])

    def test_identity_with_no_answers_gets_no_groups(self):
        self.assertEqual(briefcase_groups(identity=self.identity), [])

    def test_empty_page_is_not_rendered_as_a_group(self):
        # "Your notice" places nothing this identity answered, so it must not
        # appear as an empty heading.
        placed = self._answer("tenant_name", "Jamie")
        _place(self.about_you, placed, 0)
        unanswered = Variable.objects.create(name="hearing_date")
        _place(self.your_notice, unanswered, 0)

        groups = briefcase_groups(identity=self.identity)

        self.assertEqual([g["title"] for g in groups], ["About you"])


@pytest.mark.postgres
class BriefcaseChatContextTests(TestCase):
    def test_chat_page_exposes_the_visitors_groups(self):
        response = self.client.get(reverse("pages:chat"))
        identity = UserIdentity.objects.get(
            session_key=self.client.session.session_key
        )
        topic = Topic.objects.create(slug="eviction", order=0)
        flow = TopicFlow.objects.create(topic=topic, slug="tenant", order=0)
        page = TopicFlowInterviewPage.objects.create(
            flow=flow, title="About you", order=0
        )
        variable = Variable.objects.create(name="tenant_name", label="Name")
        VariableAnswer.objects.create(
            identity=identity, variable=variable, value="Jamie"
        )
        _place(page, variable, 0)

        response = self.client.get(reverse("pages:chat"))

        groups = response.context["briefcase_groups"]
        self.assertEqual([g["title"] for g in groups], ["About you"])
        self.assertEqual(
            [a.variable.label for a in groups[0]["answers"]], ["Name"]
        )

    def test_chat_page_exposes_empty_groups_for_a_fresh_visitor(self):
        # The panel is always rendered, so the context key must always exist:
        # a missing key and an empty list are different bugs in the template.
        response = self.client.get(reverse("pages:chat"))

        self.assertEqual(response.context["briefcase_groups"], [])


class DisplayValueTests(TestCase):
    """``VariableAnswer.display_value`` shapes jsonb for reading. No DB —
    the property only touches the in-memory value."""

    def _value(self, value):
        return VariableAnswer(value=value).display_value

    def test_list_renders_as_a_comma_separated_string(self):
        # A multi-choice answer is stored as a list; str() would print
        # "['Unpaid rent', 'Lease violation']" at the litigant.
        self.assertEqual(
            self._value(["Unpaid rent", "Lease violation"]),
            "Unpaid rent, Lease violation",
        )

    def test_single_item_list_has_no_separator(self):
        self.assertEqual(self._value(["Unpaid rent"]), "Unpaid rent")

    def test_booleans_render_as_words_not_python_literals(self):
        self.assertEqual(self._value(True), "Yes")
        self.assertEqual(self._value(False), "No")

    def test_false_is_not_treated_as_absent(self):
        # `if self.value` would collapse False to the str() branch and print
        # "False"; the isinstance check is what keeps it a real answer.
        self.assertEqual(self._value(False), "No")

    def test_strings_and_numbers_pass_through(self):
        self.assertEqual(self._value("2026-09-01"), "2026-09-01")
        self.assertEqual(self._value(28), "28")
