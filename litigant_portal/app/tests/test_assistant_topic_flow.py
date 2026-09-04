"""Postgres tests: the assistant's active topic flow — the tool that loads
it, the flow list injected into the system prompt, and stale-state
clearing."""

import pytest
from django.test import TestCase

from litigant_portal.agents.assistant import (
    LitigantAssistant,
    LitigantAssistantState,
)
from litigant_portal.agents.tools.load_topic_flow import (
    LoadTopicFlow,
    topic_flow_from_path,
    topic_flow_markdown,
    topic_flow_path,
)
from litigant_portal.app.models import (
    ChatThread,
    Form,
    Topic,
    TopicFlow,
    TopicFlowDeadline,
    TopicFlowFormCondition,
    TopicFlowInterviewPage,
    TopicFlowInterviewVariable,
    TopicFlowLink,
    TopicFlowSection,
    UserIdentity,
    Variable,
)
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.selectors.topic_flow import (
    topic_flow_find,
    topic_flow_list,
)
from litigant_portal.app.services.site import site_update


def _eviction_flow() -> TopicFlow:
    topic = Topic.objects.create(slug="eviction", title="Eviction")
    return TopicFlow.objects.create(
        topic=topic,
        slug="tenant",
        name="Responding to an Eviction",
        enabled=True,
    )


def _thread() -> ChatThread:
    identity = UserIdentity.objects.create(session_key="abc123")
    return ChatThread.objects.create(
        identity=identity, thread_type="user_chat"
    )


@pytest.mark.postgres
class TopicFlowSelectorTests(TestCase):
    def test_list_returns_only_enabled_flows(self):
        flow = _eviction_flow()
        TopicFlow.objects.create(
            topic=flow.topic,
            slug="landlord",
            name="Filing an Eviction",
            enabled=False,
        )
        self.assertEqual(topic_flow_list(), [flow])

    def test_find_returns_flow_by_slugs(self):
        flow = _eviction_flow()
        self.assertEqual(
            topic_flow_find(topic_slug="eviction", flow_slug="tenant"), flow
        )

    def test_find_returns_none_for_disabled_flow(self):
        flow = _eviction_flow()
        flow.enabled = False
        flow.save()
        self.assertIsNone(
            topic_flow_find(topic_slug="eviction", flow_slug="tenant")
        )

    def test_find_returns_none_for_unknown_slugs(self):
        self.assertIsNone(
            topic_flow_find(topic_slug="eviction", flow_slug="tenant")
        )


@pytest.mark.postgres
class TopicFlowPathTests(TestCase):
    def test_round_trip(self):
        flow = _eviction_flow()
        self.assertEqual(topic_flow_path(flow), "eviction/tenant")
        self.assertEqual(topic_flow_from_path("eviction/tenant"), flow)

    def test_malformed_paths_return_none(self):
        _eviction_flow()
        for path in ("eviction", "eviction/", "/tenant", ""):
            self.assertIsNone(topic_flow_from_path(path))


@pytest.mark.postgres
class TopicFlowMarkdownTests(TestCase):
    def test_markdown_covers_the_flow_content_graph(self):
        flow = _eviction_flow()
        TopicFlowSection.objects.create(
            flow=flow, heading="First steps", content="Read the notice."
        )
        served = Variable.objects.create(
            name="date_served",
            label="Date you were served",
            data_type=VariableDataType.DATE,
        )
        TopicFlowDeadline.objects.create(
            flow=flow, label="Answer due", offset_days=28, offset_from=served
        )
        county = Variable.objects.create(
            name="county",
            question="What county do you live in?",
            data_type=VariableDataType.CHOICE,
            choices=[{"value": "cass", "label": "Cass County"}],
        )
        lease_end = Variable.objects.create(
            name="lease_end",
            question="When does your lease end?",
            data_type=VariableDataType.DATE,
            asked_when=county,
            asked_when_value="cass",
        )
        page = TopicFlowInterviewPage.objects.create(
            flow=flow, title="About your case"
        )
        TopicFlowInterviewVariable.objects.create(page=page, variable=served)
        TopicFlowInterviewVariable.objects.create(page=page, variable=county)
        TopicFlowInterviewVariable.objects.create(
            page=page, variable=lease_end
        )
        form = Form.objects.create(slug="answer", name="Answer Form")
        TopicFlowFormCondition.objects.create(flow=flow, form=form)
        fee_waiver = Form.objects.create(slug="fee-waiver", name="Fee Waiver")
        TopicFlowFormCondition.objects.create(
            flow=flow, form=fee_waiver, variable=county, value="cass"
        )
        TopicFlowLink.objects.create(
            flow=flow, name="Court site", url="https://example.com/court"
        )

        markdown = topic_flow_markdown(
            topic_flow_find(topic_slug="eviction", flow_slug="tenant")
        )

        self.assertIn("# Responding to an Eviction", markdown)
        self.assertIn("Topic: Eviction", markdown)
        self.assertIn("## First steps", markdown)
        self.assertIn("Read the notice.", markdown)
        self.assertIn(
            "- Answer due: 28 days after Date you were served", markdown
        )
        self.assertIn("- Answer Form", markdown)
        self.assertIn(
            '- Fee Waiver (included when county equals "cass")', markdown
        )
        self.assertIn("### About your case", markdown)
        self.assertIn("- date_served (date): Date you were served", markdown)
        self.assertIn(
            "- county (choice): What county do you live in? [choices: cass]",
            markdown,
        )
        self.assertIn(
            "- lease_end (date): When does your lease end? "
            '(asked when county = "cass")',
            markdown,
        )
        self.assertIn("- Court site: https://example.com/court", markdown)

    def test_markdown_omits_empty_sections(self):
        _eviction_flow()
        markdown = topic_flow_markdown(
            topic_flow_find(topic_slug="eviction", flow_slug="tenant")
        )
        for heading in ("## Deadlines", "## Form packet", "## Links"):
            self.assertNotIn(heading, markdown)


@pytest.mark.postgres
class LoadTopicFlowToolTests(TestCase):
    def setUp(self):
        self.thread = _thread()
        self.flow = _eviction_flow()

    def test_result_names_the_active_flow_then_gives_its_markdown(self):
        output = LoadTopicFlow(topic_flow="eviction/tenant")(
            thread_id=self.thread.id
        )
        self.assertTrue(
            output.result.startswith(
                "The active topic flow is now eviction/tenant "
                "(Responding to an Eviction)."
            )
        )
        self.assertIn("# Responding to an Eviction", output.result)
        self.assertFalse(output.refresh_system_prompt)
        self.assertEqual(output.render_data["topic_flow"], "eviction/tenant")
        self.thread.refresh_from_db()
        state = LitigantAssistantState.model_validate(self.thread.state)
        self.assertEqual(state.active_topic_flow, "eviction/tenant")

    def test_preserves_other_state_keys(self):
        self.thread.state = {"other": "kept"}
        self.thread.save(update_fields=["state"])
        LoadTopicFlow(topic_flow="eviction/tenant")(thread_id=self.thread.id)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.state["other"], "kept")

    def test_unknown_flow_errors_and_writes_nothing(self):
        output = LoadTopicFlow(topic_flow="eviction/landlord")(
            thread_id=self.thread.id
        )
        self.assertIn("Error", output.result)
        self.assertIn("eviction/tenant", output.result)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.state, {})


@pytest.mark.postgres
class AssistantSystemPromptTests(TestCase):
    def setUp(self):
        self.thread = _thread()
        self.agent = LitigantAssistant()

    def test_lists_available_flows(self):
        _eviction_flow()
        prompt = self.agent.generate_system_prompt(thread_id=self.thread.id)
        self.assertIn(
            "- eviction/tenant: Responding to an Eviction (Eviction)", prompt
        )

    def test_no_flow_section_when_no_flows_exist(self):
        prompt = self.agent.generate_system_prompt(thread_id=self.thread.id)
        self.assertNotIn("Guided topic flows", prompt)

    def test_court_context_from_site_config(self):
        with self.captureOnCommitCallbacks(execute=True):
            site_update(
                court_name="Alpha District Court",
                jurisdiction_level="state",
                state="ND",
                official_url="https://alpha.test",
                official_resources_url="https://alpha.test/help",
            )
        prompt = self.agent.generate_system_prompt(thread_id=self.thread.id)
        self.assertIn("## Court context", prompt)
        self.assertIn("You are operating in Alpha District Court.", prompt)
        self.assertIn("- Jurisdiction level: State", prompt)
        self.assertIn("- State: North Dakota", prompt)
        self.assertIn("- Court website: https://alpha.test", prompt)
        self.assertIn(
            "- Court self-help resources: https://alpha.test/help", prompt
        )

    def test_court_context_omits_blank_fields(self):
        with self.captureOnCommitCallbacks(execute=True):
            site_update(court_name="Alpha District Court")
        prompt = self.agent.generate_system_prompt(thread_id=self.thread.id)
        self.assertIn("You are operating in Alpha District Court.", prompt)
        self.assertNotIn("Jurisdiction level", prompt)
        self.assertNotIn("- State:", prompt)
        self.assertNotIn("Court website", prompt)
        self.assertNotIn("self-help resources", prompt)

    def test_blank_court_name_means_multi_court_mode(self):
        prompt = self.agent.generate_system_prompt(thread_id=self.thread.id)
        self.assertIn("## Court context", prompt)
        self.assertIn("multi-court mode", prompt)
        self.assertNotIn("You are operating in", prompt)

    def test_prompt_ignores_the_active_flow(self):
        # The prompt depends only on the enabled-flow list, never on
        # per-thread state, so all threads share one cached prompt
        # artifact.
        _eviction_flow()
        before = self.agent.generate_system_prompt(thread_id=self.thread.id)
        self.thread.state = {"active_topic_flow": "eviction/tenant"}
        self.thread.save(update_fields=["state"])
        after = self.agent.generate_system_prompt(thread_id=self.thread.id)
        self.assertEqual(before, after)


@pytest.mark.postgres
class AssistantPrepareThreadTests(TestCase):
    def setUp(self):
        self.thread = _thread()
        self.agent = LitigantAssistant()

    def test_clears_a_stale_active_flow(self):
        _eviction_flow()
        self.thread.state = {"active_topic_flow": "eviction/gone"}
        self.thread.save(update_fields=["state"])
        self.agent.prepare_thread(thread_id=self.thread.id)
        self.thread.refresh_from_db()
        self.assertIsNone(self.thread.state["active_topic_flow"])

    def test_keeps_a_valid_active_flow(self):
        _eviction_flow()
        self.thread.state = {"active_topic_flow": "eviction/tenant"}
        self.thread.save(update_fields=["state"])
        self.agent.prepare_thread(thread_id=self.thread.id)
        self.thread.refresh_from_db()
        self.assertEqual(
            self.thread.state["active_topic_flow"], "eviction/tenant"
        )

    def test_ignores_a_thread_with_no_active_flow(self):
        self.agent.prepare_thread(thread_id=self.thread.id)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.state, {})
