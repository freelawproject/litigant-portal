"""Tests for topic flow answer writes and the ``reviewed`` flag.

``reviewed`` is what tells a later reader whether a human actually looked at
a value or an agent guessed it, so it has to track the writer — including on
overwrite, where a stale True would be worse than never having the flag.
"""

from django.test import TestCase
from django.urls import reverse

from litigant_portal.app.models import (
    Topic,
    TopicFlow,
    TopicFlowAnswer,
    TopicFlowField,
    TopicFlowFieldGroup,
    UserIdentity,
)
from litigant_portal.app.selectors.topic_flow import topic_flow_get_public
from litigant_portal.app.services.topic_flow import topic_flow_answers_update


class TopicFlowAnswersUpdateTests(TestCase):
    def setUp(self):
        topic = Topic.objects.create(slug="name-change", title="Name change")
        self.flow = TopicFlow.objects.create(
            topic=topic, slug="standard", name="Standard", enabled=True
        )
        group = TopicFlowFieldGroup.objects.create(
            flow=self.flow, title="About you", order=0
        )
        self.field = TopicFlowField.objects.create(
            group=group, name="full_name", data_type="text", order=0
        )
        self.identity = UserIdentity.objects.create(session_key="abc123")

    def _answer(self):
        return TopicFlowAnswer.objects.get(
            identity=self.identity, field=self.field
        )

    def test_human_write_marks_reviewed(self):
        topic_flow_answers_update(
            identity=self.identity,
            flow=self.flow,
            answers={"full_name": "Jane Doe"},
            reviewed=True,
        )
        answer = self._answer()
        self.assertEqual(answer.value, "Jane Doe")
        self.assertTrue(answer.reviewed)

    def test_agent_write_leaves_unreviewed(self):
        topic_flow_answers_update(
            identity=self.identity,
            flow=self.flow,
            answers={"full_name": "Jane Doe"},
            reviewed=False,
        )
        self.assertFalse(self._answer().reviewed)

    def test_blank_value_deletes_the_answer(self):
        """What the rail's Clear button relies on: it wipes answers by
        POSTing every field blank rather than through its own endpoint."""
        topic_flow_answers_update(
            identity=self.identity,
            flow=self.flow,
            answers={"full_name": "Jane Doe"},
            reviewed=True,
        )
        values = topic_flow_answers_update(
            identity=self.identity,
            flow=self.flow,
            answers={"full_name": ""},
            reviewed=True,
        )
        self.assertEqual(values, {})
        self.assertFalse(TopicFlowAnswer.objects.exists())

    def test_agent_overwrite_clears_a_prior_review(self):
        """A new value hasn't been reviewed just because the old one was."""
        topic_flow_answers_update(
            identity=self.identity,
            flow=self.flow,
            answers={"full_name": "Jane Doe"},
            reviewed=True,
        )
        topic_flow_answers_update(
            identity=self.identity,
            flow=self.flow,
            answers={"full_name": "Jane Q. Doe"},
            reviewed=False,
        )
        answer = self._answer()
        self.assertEqual(answer.value, "Jane Q. Doe")
        self.assertFalse(answer.reviewed)


class FlowAnswersViewTests(TestCase):
    """The public endpoint is the human path, so its writes are reviewed."""

    def setUp(self):
        topic = Topic.objects.create(slug="name-change", title="Name change")
        self.flow = TopicFlow.objects.create(
            topic=topic, slug="standard", name="Standard", enabled=True
        )
        group = TopicFlowFieldGroup.objects.create(
            flow=self.flow, title="About you", order=0
        )
        TopicFlowField.objects.create(
            group=group, name="full_name", data_type="text", order=0
        )

    def test_post_marks_answers_reviewed(self):
        response = self.client.post(
            reverse(
                "topic_flow_api:answers",
                kwargs={"topic_slug": "name-change", "flow_slug": "standard"},
            ),
            data={"answers": {"full_name": "Jane Doe"}},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["answers"], {"full_name": "Jane Doe"})
        answer = TopicFlowAnswer.objects.get()
        self.assertEqual(answer.value, "Jane Doe")
        self.assertTrue(answer.reviewed)

    def test_client_cannot_claim_a_review_it_did_not_do(self):
        """``reviewed`` is decided server-side; a body flag is ignored."""
        self.client.post(
            reverse(
                "topic_flow_api:answers",
                kwargs={"topic_slug": "name-change", "flow_slug": "standard"},
            ),
            data={"answers": {"full_name": "Jane"}, "reviewed": False},
            content_type="application/json",
        )
        self.assertTrue(TopicFlowAnswer.objects.get().reviewed)


class InterviewPayloadTests(TestCase):
    """The flow page ships its interview as grouped steps, not a flat list."""

    def setUp(self):
        topic = Topic.objects.create(slug="name-change", title="Name change")
        self.flow = TopicFlow.objects.create(
            topic=topic, slug="standard", name="Standard", enabled=True
        )
        about = TopicFlowFieldGroup.objects.create(
            flow=self.flow, title="About you", order=0
        )
        TopicFlowField.objects.create(
            group=about, name="full_name", data_type="text", order=0
        )
        TopicFlowField.objects.create(
            group=about,
            name="agrees",
            data_type="boolean",
            default="true",
            order=1,
        )
        TopicFlowField.objects.create(
            group=about, name="hearing_at", data_type="datetime", order=2
        )
        TopicFlowField.objects.create(
            group=about, name="filed_on", data_type="date", order=3
        )
        # An empty group is a dead click in the wizard and must be dropped.
        TopicFlowFieldGroup.objects.create(
            flow=self.flow, title="Nothing here", order=1
        )

    def _values(self, answers):
        from litigant_portal.app.views.topic_flow import _interview_payload

        flow = topic_flow_get_public(
            topic_slug="name-change", flow_slug="standard"
        )
        return {
            f["name"]: f["value"]
            for f in _interview_payload(flow, answers)["steps"][0]["fields"]
        }

    def test_payload_groups_fields_into_steps(self):
        from litigant_portal.app.views.topic_flow import _interview_payload

        flow = topic_flow_get_public(
            topic_slug="name-change", flow_slug="standard"
        )
        payload = _interview_payload(flow, {"full_name": "Jane"})
        self.assertEqual(len(payload["steps"]), 1)
        step = payload["steps"][0]
        self.assertEqual(step["title"], "About you")
        names = [f["name"] for f in step["fields"]]
        self.assertEqual(
            names, ["full_name", "agrees", "hearing_at", "filed_on"]
        )
        self.assertEqual(step["fields"][0]["value"], "Jane")

    def test_boolean_default_coerces_to_a_real_bool(self):
        """A checkbox binding needs true, not the string "true"."""
        from litigant_portal.app.views.topic_flow import _interview_payload

        flow = topic_flow_get_public(
            topic_slug="name-change", flow_slug="standard"
        )
        payload = _interview_payload(flow, {})
        agrees = payload["steps"][0]["fields"][1]
        self.assertIs(agrees["value"], True)

    def test_datetime_keeps_its_time(self):
        """``topic_flow_field_value`` truncates datetimes to a date for the
        deadline math. The interview must not: a date-only string is invalid
        for ``datetime-local``, so the input would render empty and stepping
        past it would post a blank and delete the answer."""
        values = self._values({"hearing_at": "2026-01-15T10:30:00"})
        self.assertEqual(values["hearing_at"], "2026-01-15T10:30")

    def test_date_ships_as_an_iso_string(self):
        values = self._values({"filed_on": "2026-01-15"})
        self.assertEqual(values["filed_on"], "2026-01-15")

    def test_unanswered_fields_ship_empty(self):
        values = self._values({})
        self.assertEqual(values["hearing_at"], "")
        self.assertEqual(values["filed_on"], "")
        self.assertEqual(values["full_name"], "")
