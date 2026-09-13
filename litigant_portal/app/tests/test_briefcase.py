"""The briefcase panel's grouping selector and its chat-page context.

The panel shows an identity's stored facts grouped for reading. Grouping is
derived from each answered variable's own interview placement, not from an
"active flow" — the chat page has no flow server-side, so a placement-driven
grouping is the only one available without a model change.
"""

import pytest
from django.test import SimpleTestCase, TestCase
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
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.selectors.topic_flow import variable_answer_groups
from litigant_portal.app.views.pages import _briefcase_sample


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
            topic=self.topic, slug="tenant", order=0, enabled=True
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

        groups = variable_answer_groups(identity=self.identity)

        self.assertEqual(
            [g["title"] for g in groups], ["About you", "Your notice"]
        )

    def test_variables_within_a_group_follow_placement_order(self):
        last = self._answer("tenant_last", "Rivera")
        first = self._answer("tenant_first", "Jamie")
        # Placement order is deliberately the reverse of alphabetical.
        _place(self.about_you, first, 0)
        _place(self.about_you, last, 1)

        groups = variable_answer_groups(identity=self.identity)

        self.assertEqual(
            [a.variable.name for a in groups[0]["answers"]],
            ["tenant_first", "tenant_last"],
        )

    def test_unplaced_answers_land_in_a_titleless_group_last(self):
        placed = self._answer("tenant_name", "Jamie")
        _place(self.about_you, placed, 0)
        self._answer("court_name", "Franklin County Municipal Court")

        groups = variable_answer_groups(identity=self.identity)

        self.assertEqual(groups[-1]["title"], "")
        self.assertEqual(
            [a.variable.name for a in groups[-1]["answers"]], ["court_name"]
        )

    def test_no_titleless_group_when_every_answer_is_placed(self):
        placed = self._answer("tenant_name", "Jamie")
        _place(self.about_you, placed, 0)

        groups = variable_answer_groups(identity=self.identity)

        self.assertEqual([g["title"] for g in groups], ["About you"])

    def test_cleared_answers_are_left_out(self):
        # A None value is a cleared answer, not a fact. Showing the label with
        # an empty value reads as "we know this and it's blank".
        kept = self._answer("tenant_name", "Jamie")
        cleared = self._answer("hearing_date", None)
        _place(self.about_you, kept, 0)
        _place(self.about_you, cleared, 1)

        groups = variable_answer_groups(identity=self.identity)

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

        groups = variable_answer_groups(identity=self.identity)

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

        self.assertEqual(variable_answer_groups(identity=self.identity), [])

    def test_identity_with_no_answers_gets_no_groups(self):
        self.assertEqual(variable_answer_groups(identity=self.identity), [])

    def test_a_disabled_flows_page_is_not_used_for_grouping(self):
        # enabled defaults to False, so a draft flow is the normal state of a
        # half-authored one. Its page title heading a real litigant's
        # briefcase would leak unpublished corpus at them.
        draft = TopicFlow.objects.create(
            topic=self.topic, slug="landlord", order=1, enabled=False
        )
        draft_page = TopicFlowInterviewPage.objects.create(
            flow=draft, title="Draft page", order=0
        )
        answered = self._answer("tenant_name", "Jamie")
        _place(draft_page, answered, 0)

        groups = variable_answer_groups(identity=self.identity)

        self.assertEqual([g["title"] for g in groups], [""])

    def test_empty_page_is_not_rendered_as_a_group(self):
        # "Your notice" places nothing this identity answered, so it must not
        # appear as an empty heading.
        placed = self._answer("tenant_name", "Jamie")
        _place(self.about_you, placed, 0)
        unanswered = Variable.objects.create(name="hearing_date")
        _place(self.your_notice, unanswered, 0)

        groups = variable_answer_groups(identity=self.identity)

        self.assertEqual([g["title"] for g in groups], ["About you"])


@pytest.mark.postgres
class BriefcaseChatContextTests(TestCase):
    def test_chat_page_exposes_the_visitors_groups(self):
        # Seed the identity the middleware will resolve, rather than letting a
        # GET mint one: an anonymous first paint no longer creates a row.
        self.client.session.save()
        identity = UserIdentity.objects.create(
            session_key=self.client.session.session_key
        )
        topic = Topic.objects.create(slug="eviction", order=0)
        flow = TopicFlow.objects.create(
            topic=topic, slug="tenant", order=0, enabled=True
        )
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

    def test_no_unrendered_template_syntax_reaches_the_page(self):
        # Django's {# #} comment is single-line only, so a multi-line one is
        # not a comment and renders as body text. That shipped once, straight
        # into the briefcase panel.
        content = self.client.get(reverse("pages:chat")).content.decode()

        self.assertNotIn("{#", content)
        self.assertNotIn("{%", content)

    def test_chat_page_for_a_first_time_visitor_creates_no_identity(self):
        # Reading through request.identity mints a session and a UserIdentity
        # row, so an unguarded read banks one per anonymous hit, crawlers
        # included. views/utils.topic_flow_answers already guards this.
        self.client.get(reverse("pages:chat"))

        self.assertEqual(UserIdentity.objects.count(), 0)

    def test_chat_page_exposes_empty_groups_for_a_fresh_visitor(self):
        # The panel is always rendered, so the context key must always exist:
        # a missing key and an empty list are different bugs in the template.
        response = self.client.get(reverse("pages:chat"))

        self.assertEqual(response.context["briefcase_groups"], [])


class DisplayValueTests(SimpleTestCase):
    """``VariableAnswer.display_value`` shapes jsonb for reading. No DB —
    the property only touches in-memory objects, so SimpleTestCase keeps it
    out of the suite's database path."""

    def _value(self, value, data_type=VariableDataType.TEXT):
        return VariableAnswer(
            variable=Variable(name="v", data_type=data_type), value=value
        ).display_value

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

    def test_dates_render_long_form_not_iso(self):
        # The corpus stores an ISO string in jsonb; "2026-09-09" in front of a
        # litigant is a machine's date. Shape matches the flow page's
        # deadlines (format_long_date) so one date reads the same on both.
        self.assertEqual(
            self._value("2026-09-09", VariableDataType.DATE),
            "Wednesday, September 9, 2026",
        )

    def test_an_unparseable_date_falls_back_to_the_stored_value(self):
        # Never swallow a value we can't parse — the litigant still needs to
        # see whatever is actually stored against their case.
        self.assertEqual(
            self._value("next Tuesday", VariableDataType.DATE),
            "next Tuesday",
        )

    def test_a_text_variable_holding_a_date_string_is_left_alone(self):
        # Formatting keys off the variable's declared type, not the shape of
        # the string, so a case number that looks like a date stays intact.
        self.assertEqual(
            self._value("2026-09-09", VariableDataType.TEXT), "2026-09-09"
        )

    def test_an_answer_with_no_variable_still_renders(self):
        self.assertEqual(VariableAnswer(value="Jamie").display_value, "Jamie")

    def test_a_cleared_answer_renders_empty_not_none(self):
        self.assertEqual(VariableAnswer(value=None).display_value, "")


class BriefcaseSampleTests(SimpleTestCase):
    """The style guide's in-memory sample. No DB: it builds unsaved rows."""

    def _fact(self, name):
        return next(
            answer
            for group in _briefcase_sample()
            for answer in group["answers"]
            if answer.variable.name == name
        )

    def test_the_date_fact_renders_in_the_apps_date_format(self):
        # Without a data_type the variable defaults to TEXT, so the sample
        # shows a raw ISO string where a real briefcase shows a long date, and
        # the style guide then documents output the panel never produces.
        self.assertEqual(
            self._fact("received_date").display_value,
            "Tuesday, September 1, 2026",
        )

    def test_a_plain_text_fact_is_untouched(self):
        self.assertEqual(self._fact("tenant_first").display_value, "Jamie")
