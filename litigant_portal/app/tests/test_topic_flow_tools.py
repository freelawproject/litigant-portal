"""Tests for the assistant's topic flow tools and the flow summary API.

The tools are the agent-side writers of the same answer store the flow
page's interview uses, so the important properties are: agent writes stay
``reviewed=False``, validation failures save nothing, and the active-flow
pointer round-trips through thread state.
"""

import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from pypdf import PdfWriter

from litigant_portal.agents import LitigantAssistant, LitigantAssistantState
from litigant_portal.agents.tools.topic_flow import (
    LoadTopicFlow,
    ReadForm,
    SetActiveTopicFlow,
    UpdateTopicFlowFields,
)
from litigant_portal.app.models import (
    ChatThread,
    Topic,
    TopicFlow,
    TopicFlowAnswer,
    TopicFlowField,
    TopicFlowFieldGroup,
    TopicFlowForm,
    TopicFlowFormField,
    TopicFlowSection,
    UserIdentity,
)


def _blank_pdf() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def _build_flow():
    """One live flow with two fields, a section, and a two-mapping form."""
    topic = Topic.objects.create(slug="eviction", title="Eviction")
    flow = TopicFlow.objects.create(
        topic=topic,
        slug="respond",
        name="Respond to an Eviction",
        enabled=True,
    )
    group = TopicFlowFieldGroup.objects.create(flow=flow, order=0)
    TopicFlowField.objects.create(
        group=group,
        name="full_name",
        label="Your full name",
        data_type="text",
        order=0,
    )
    TopicFlowField.objects.create(
        group=group, name="hearing_date", data_type="date", order=1
    )
    TopicFlowSection.objects.create(
        flow=flow, heading="About", content="How it works.", order=0
    )
    form = TopicFlowForm.objects.create(
        flow=flow,
        slug="appearance",
        name="Appearance",
        file=SimpleUploadedFile("appearance.pdf", _blank_pdf()),
    )
    TopicFlowFormField.objects.create(
        form=form, pdf_field="name", template="{full_name}", order=0
    )
    TopicFlowFormField.objects.create(
        form=form, pdf_field="hearing", template="{hearing_date}", order=1
    )
    return flow


class TopicFlowToolTests(TestCase):
    def setUp(self):
        self.flow = _build_flow()
        self.identity = UserIdentity.objects.create(session_key="abc123")
        self.thread = ChatThread.objects.create(identity=self.identity)

    def _state(self) -> LitigantAssistantState:
        self.thread.refresh_from_db()
        return LitigantAssistantState.model_validate(self.thread.state)

    def _set_active(self):
        return SetActiveTopicFlow(topic_slug="eviction", flow_slug="respond")(
            thread_id=self.thread.id
        )

    def test_set_active_topic_flow_writes_state(self):
        output = self._set_active()
        self.assertTrue(output.refresh_system_prompt)
        ref = self._state().active_topic_flow
        self.assertEqual(ref.topic_slug, "eviction")
        self.assertEqual(ref.flow_slug, "respond")
        self.assertEqual(
            ref.summary_url,
            reverse(
                "topic_flow_api:summary",
                kwargs={"topic_slug": "eviction", "flow_slug": "respond"},
            ),
        )

    def test_set_active_topic_flow_unknown_lists_catalog(self):
        output = SetActiveTopicFlow(topic_slug="eviction", flow_slug="nope")(
            thread_id=self.thread.id
        )
        self.assertIn("Error", output.result)
        self.assertIn(
            'topic_slug "eviction", flow_slug "respond"', output.result
        )
        self.assertIsNone(self._state().active_topic_flow)

    def test_set_active_topic_flow_repairs_combined_pair(self):
        """Small models pass the catalog pair as the topic_slug; the
        resolver repairs it and the state stores canonical slugs."""
        output = SetActiveTopicFlow(
            topic_slug="eviction/respond", flow_slug="junk"
        )(thread_id=self.thread.id)
        self.assertTrue(output.refresh_system_prompt)
        ref = self._state().active_topic_flow
        self.assertEqual(ref.topic_slug, "eviction")
        self.assertEqual(ref.flow_slug, "respond")

    def test_set_active_topic_flow_accepts_display_name(self):
        SetActiveTopicFlow(
            topic_slug="eviction", flow_slug="Respond to an Eviction"
        )(thread_id=self.thread.id)
        ref = self._state().active_topic_flow
        self.assertEqual(ref.flow_slug, "respond")

    def test_update_fields_requires_active_flow(self):
        output = UpdateTopicFlowFields(fields={"full_name": "Jane Roe"})(
            thread_id=self.thread.id
        )
        self.assertIn("no active guide", output.result)
        self.assertFalse(TopicFlowAnswer.objects.exists())

    def test_update_fields_saves_unreviewed_and_reports_unknown(self):
        self._set_active()
        output = UpdateTopicFlowFields(
            fields={"full_name": "Jane Roe", "bogus": "x"}
        )(thread_id=self.thread.id)
        answer = TopicFlowAnswer.objects.get(
            identity=self.identity, field__name="full_name"
        )
        self.assertEqual(answer.value, "Jane Roe")
        self.assertFalse(answer.reviewed)
        self.assertTrue(output.refresh_system_prompt)
        self.assertIn("bogus", output.result)
        self.assertEqual(output.render_data["saved"], ["Your full name"])

    def test_update_fields_invalid_value_saves_nothing(self):
        self._set_active()
        output = UpdateTopicFlowFields(
            fields={"full_name": "Jane Roe", "hearing_date": "not-a-date"}
        )(thread_id=self.thread.id)
        self.assertIn("Error", output.result)
        self.assertFalse(TopicFlowAnswer.objects.exists())

    def test_load_topic_flow_includes_content_and_status(self):
        output = LoadTopicFlow(topic_slug="eviction", flow_slug="respond")(
            thread_id=self.thread.id
        )
        self.assertIn("## About", output.result)
        self.assertIn("How it works.", output.result)
        self.assertIn("full_name", output.result)
        self.assertIn("not answered", output.result)
        self.assertIn("appearance", output.result)

    def test_read_form_reports_fill_status(self):
        self._set_active()
        UpdateTopicFlowFields(fields={"full_name": "Jane Roe"})(
            thread_id=self.thread.id
        )
        output = ReadForm(form_slug="appearance")(thread_id=self.thread.id)
        self.assertIn("1 of 2", output.result)
        self.assertIn("Jane Roe", output.result)
        self.assertEqual(output.render_data["missing"], ["hearing_date"])

    def test_read_form_unknown_slug_lists_forms(self):
        self._set_active()
        output = ReadForm(form_slug="nope")(thread_id=self.thread.id)
        self.assertIn("Error", output.result)
        self.assertIn("appearance", output.result)

    def test_system_prompt_lists_guides_and_active_status(self):
        agent = LitigantAssistant()
        prompt = agent.generate_system_prompt(thread_id=self.thread.id)
        self.assertIn('topic_slug "eviction", flow_slug "respond"', prompt)
        self.assertNotIn("ACTIVE GUIDE", prompt)
        self._set_active()
        prompt = agent.generate_system_prompt(thread_id=self.thread.id)
        self.assertIn("ACTIVE GUIDE", prompt)
        self.assertIn("full_name", prompt)


class TopicFlowSummaryViewTests(TestCase):
    def setUp(self):
        self.flow = _build_flow()
        self.url = reverse(
            "topic_flow_api:summary",
            kwargs={"topic_slug": "eviction", "flow_slug": "respond"},
        )

    def test_summary_returns_progress_and_forms(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "Respond to an Eviction")
        self.assertEqual(data["topic_title"], "Eviction")
        self.assertEqual(data["progress"]["answered"], 0)
        self.assertEqual(data["progress"]["total"], 2)
        self.assertEqual(
            [form["slug"] for form in data["forms"]], ["appearance"]
        )
        self.assertTrue(data["packet_url"])

    def test_summary_404_for_unknown_flow(self):
        response = self.client.get(
            reverse(
                "topic_flow_api:summary",
                kwargs={"topic_slug": "eviction", "flow_slug": "nope"},
            )
        )
        self.assertEqual(response.status_code, 404)
