"""
Access gates and host configuration for the new agent development page.
"""

import asyncio
import json
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from pydantic import ValidationError

from litigant_portal.app.models.choices import (
    DEFAULT_BEDROCK_MODEL,
    BedrockModel,
)
from litigant_portal.app.permissions import ADMINS_GROUP, DEVELOPERS_GROUP
from litigant_portal.app.selectors.agent import agent_scope_choices
from litigant_portal.app.services.site import site_update
from litigant_portal.app.views.agent import AgentMessageForm
from lp_agent import AgentValidationError, RunLimits
from lp_agent.adapters.bedrock import MODEL_CHOICES
from lp_agent.errors import ModelProviderError
from lp_agent.flows.new_engagement import message_text
from lp_agent.tests.fixtures.preparation import load_preparation_fixture
from lp_agent.tests.helpers import answer_item
from lp_agent.tests.providers.test_database import database
from lp_agent.tests.providers.test_database import (
    database_dsns as database_dsns,  # noqa: F401
)
from lp_agent.types import ModelFinished, ModelMessage, ModelTextDelta


@pytest.fixture(scope="module")
def agent_database(database_dsns):  # noqa: F811
    async def seed():
        async with database(database_dsns["crud"]) as db:
            await load_preparation_fixture(db, settings.BASE_DIR)

    with override_settings(
        LP_AGENT_USE_DJANGO_DB=False,
        LP_AGENT_WRITER_DSN=database_dsns["crud"],
        LP_AGENT_LOOKUP_DSN=database_dsns["lookup"],
    ):
        asyncio.run(seed())
        yield


@override_settings(LP_AGENT_DEV_ENABLED=True, SITE_PASSWORD="")
@pytest.mark.postgres
@pytest.mark.usefixtures("agent_database")
class AgentDevelopmentPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.developer = get_user_model().objects.create_user(username="dev")
        cls.developer.groups.add(Group.objects.get(name=DEVELOPERS_GROUP))
        cls.admin = get_user_model().objects.create_user(username="admin")
        cls.admin.groups.add(Group.objects.get(name=ADMINS_GROUP))

    def setUp(self):
        self.url = reverse("pages:agent_development")

    def test_signed_out_visitors_are_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertRedirects(
            response,
            f"{reverse('account_login')}?next={self.url}",
            fetch_redirect_response=False,
        )

    def test_signed_in_non_developers_cannot_open_the_page(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    @override_settings(LP_AGENT_DEV_ENABLED=False)
    def test_disabled_page_is_unavailable_to_developers(self):
        self.client.force_login(self.developer)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_developer_sees_site_default_and_scope_choices(self):
        self.client.force_login(self.developer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertRegex(
            response.content.decode(), r"agent_development\.js\?v=[0-9a-f]{12}"
        )
        self.assertEqual(
            response.context["selected_model"], DEFAULT_BEDROCK_MODEL
        )
        self.assertEqual(response.context["model_choices"], MODEL_CHOICES)
        court = response.context["courts"][0]
        self.assertTrue(court.topics)
        topic = court.topics[0]
        self.assertContains(
            response,
            f'<option value="{topic.choice_id}" '
            f'data-court="{court.choice_id}" x-data="agentTopicOption" '
            'x-bind:hidden="unavailable" x-bind:disabled="unavailable">'
            f"{topic.label}</option>",
            html=True,
        )

    def test_page_uses_the_configured_assistant_model(self):
        with self.captureOnCommitCallbacks(execute=True):
            site_update(assistant_model=BedrockModel.GPT_5_6_SOL)
        self.client.force_login(self.developer)
        response = self.client.get(self.url)
        self.assertEqual(
            response.context["selected_model"], BedrockModel.GPT_5_6_SOL
        )

    def test_unsupported_site_default_requires_explicit_model_selection(self):
        with self.captureOnCommitCallbacks(execute=True):
            site_update(assistant_model=BedrockModel.CLAUDE_HAIKU_4_5)
        self.client.force_login(self.developer)
        response = self.client.get(self.url)
        self.assertIsNone(response.context["selected_model"])
        self.assertContains(response, "assistant model is unavailable here")
        self.assertContains(
            response,
            '<option value="" selected>Choose model</option>',
            html=True,
        )
        self.assertRegex(
            response.content.decode(),
            r'<select[^>]*id="agent-model"[^>]*required',
        )
        self.assertNotContains(response, BedrockModel.CLAUDE_HAIKU_4_5)

    def test_page_does_not_accept_message_submissions(self):
        self.client.force_login(self.developer)
        response = self.client.post(self.url, {"message": "Hello"})
        self.assertEqual(response.status_code, 405)


class AgentModelChoicesTests(SimpleTestCase):
    def test_adapter_models_match_application_choices_with_explicit_exclusions(
        self,
    ):
        unsupported = {BedrockModel.CLAUDE_HAIKU_4_5}
        self.assertEqual(
            dict(MODEL_CHOICES),
            {
                model: label
                for model, label in BedrockModel.choices
                if model not in unsupported
            },
        )


@pytest.mark.postgres
@pytest.mark.usefixtures("agent_database")
class AgentScopeChoicesTests(SimpleTestCase):
    @override_settings(CORPUS_COURT=None)
    def test_multi_court_choices_preserve_valid_pairs(self):
        courts = agent_scope_choices()
        self.assertEqual(
            {
                (court.choice_id, topic.choice_id)
                for court in courts
                for topic in court.topics
            },
            {
                ("north-dakota", "adult-name-change"),
                ("franklin-county-oh", "eviction"),
            },
        )

    @override_settings(CORPUS_COURT="north-dakota")
    def test_single_court_filters_both_selectors(self):
        courts = agent_scope_choices()
        self.assertEqual(
            [court.choice_id for court in courts], ["north-dakota"]
        )
        self.assertEqual(
            [topic.choice_id for topic in courts[0].topics],
            ["adult-name-change"],
        )

    @override_settings(CORPUS_COURT="missing-court")
    def test_unknown_configured_court_exposes_no_choices(self):
        self.assertEqual(agent_scope_choices(), ())

    @override_settings(CORPUS_COURT=None)
    def test_form_accepts_partial_scopes_and_rejects_wrong_pairs(self):
        courts = agent_scope_choices()
        data = {
            "message": "Hello",
            "model": MODEL_CHOICES[0][0],
            "max_active_seconds": "5",
        }
        for scope in (
            {},
            {"court": "north-dakota"},
            {"topic": "adult-name-change"},
            {"court": "north-dakota", "topic": "adult-name-change"},
        ):
            form = AgentMessageForm(data | scope, courts=courts)
            self.assertTrue(form.is_valid(), form.errors)
        form = AgentMessageForm(
            data | {"court": "north-dakota", "topic": "eviction"},
            courts=courts,
        )
        self.assertFalse(form.is_valid())
        self.assertEqual(set(form.errors), {"topic"})


@override_settings(
    LP_AGENT_DEV_ENABLED=True,
    SITE_PASSWORD="",
    CORPUS_COURT=None,
    BEDROCK_API_KEY="test-only-key",
)
@pytest.mark.postgres
@pytest.mark.usefixtures("agent_database")
class AgentDevelopmentStreamTests(TestCase):
    def close_response(self, response):
        """
        Close the test client's wrapper so its connection guard runs.
        """
        if not response.closed:
            response._iterator.close()

    @classmethod
    def setUpTestData(cls):
        cls.developer = get_user_model().objects.create_user(
            username="stream-dev"
        )
        cls.developer.groups.add(Group.objects.get(name=DEVELOPERS_GROUP))
        cls.other = get_user_model().objects.create_user(username="non-dev")

    def setUp(self):
        self.url = reverse("pages:agent_development_stream")
        self.client.force_login(self.developer)
        court = next(court for court in agent_scope_choices() if court.topics)
        self.data = {
            "message": "  Hello  ",
            "court": court.choice_id,
            "topic": court.topics[0].choice_id,
            "model": BedrockModel.GPT_5_6_LUNA,
            "max_active_seconds": "5",
        }

    def test_stream_requires_login_permission_flag_post_and_csrf(self):
        agent = self.enterContext(
            patch("litigant_portal.app.views.agent.PortalAgent")
        )
        self.assertRedirects(
            Client().post(self.url, self.data),
            f"{reverse('account_login')}?next={self.url}",
            fetch_redirect_response=False,
        )
        self.client.force_login(self.other)
        response = self.client.post(self.url, self.data)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertEqual(response.json(), {"error": "Forbidden"})
        self.client.force_login(self.developer)
        with self.settings(LP_AGENT_DEV_ENABLED=False):
            self.assertEqual(
                self.client.post(self.url, self.data).status_code, 404
            )
        self.assertEqual(self.client.get(self.url).status_code, 405)
        protected = Client(enforce_csrf_checks=True)
        protected.force_login(self.developer)
        self.assertEqual(protected.post(self.url, self.data).status_code, 403)
        agent.assert_not_called()

    def test_invalid_inputs_never_construct_an_agent(self):
        cases = [
            {"message": "   "},
            {"court": "missing"},
            {"topic": "missing"},
            {"model": ""},
            {"model": "https://other.example/model"},
            {"model": BedrockModel.CLAUDE_HAIKU_4_5},
            {"max_active_seconds": "nan"},
            {"max_active_seconds": "0"},
        ]
        with patch("litigant_portal.app.views.agent.PortalAgent") as agent:
            for invalid in cases:
                with self.subTest(invalid=invalid):
                    response = self.client.post(self.url, self.data | invalid)
                    self.assertEqual(response.status_code, 400)
                    if model := invalid.get("model"):
                        self.assertNotIn(model, response.content.decode())
            with self.settings(CORPUS_COURT="unavailable"):
                self.assertEqual(
                    self.client.post(self.url, self.data).status_code, 400
                )
            agent.assert_not_called()

    def test_missing_server_key_returns_503_and_logs_a_safe_warning(self):
        with patch("litigant_portal.app.views.agent.PortalAgent") as agent:
            for key in ("", " \n\t"):
                with self.subTest(key=key), self.settings(BEDROCK_API_KEY=key):
                    with self.assertLogs(
                        "litigant_portal.app.views.agent", level="WARNING"
                    ) as logs:
                        response = self.client.post(self.url, self.data)
                    self.assertEqual(response.status_code, 503)
                    self.assertEqual(
                        response.json(),
                        {
                            "error": "Agent service is unavailable. Please try again later."
                        },
                    )
                    self.assertEqual(len(logs.records), 1)
                    self.assertIn("Bedrock API key is missing", logs.output[0])
            agent.assert_not_called()

    @override_settings(BEDROCK_API_KEY="")
    def test_invalid_input_still_returns_400_when_the_server_key_is_missing(
        self,
    ):
        with patch("litigant_portal.app.views.agent.PortalAgent") as agent:
            with self.assertNoLogs(
                "litigant_portal.app.views.agent", level="WARNING"
            ):
                response = self.client.post(
                    self.url, self.data | {"message": ""}
                )
            self.assertEqual(response.status_code, 400)
            agent.assert_not_called()

    def test_initialization_validation_errors_are_logged_without_private_details(
        self,
    ):
        with self.assertRaises(ValidationError) as validation:
            RunLimits(max_active_seconds="private invalid limit")
        for failure in (
            AgentValidationError("private initialization failure"),
            validation.exception,
        ):
            with self.subTest(failure=type(failure).__name__):
                with (
                    patch(
                        "litigant_portal.app.views.agent.PortalAgent",
                        side_effect=failure,
                    ),
                    self.assertLogs(
                        "litigant_portal.app.views.agent", level="WARNING"
                    ) as logs,
                ):
                    response = self.client.post(self.url, self.data)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(
                    response.json(), {"error": "Invalid agent configuration."}
                )
                self.assertNotIn(
                    "private", response.content.decode() + "".join(logs.output)
                )
                self.assertTrue(
                    all(record.exc_info is None for record in logs.records)
                )

    def test_http_stream_delivers_status_before_checked_answer(self):
        continue_response = asyncio.Event()
        closed = False
        requests = []

        async def model_stream(client, request):
            nonlocal closed
            if request.instructions.startswith("You review candidate"):
                yield answer_item('{"approved": true, "findings": []}')
                yield ModelFinished(reason="stop")
                return
            requests.append((client.model, request))
            try:
                yield ModelTextDelta(delta="First")
                # The provider waits while the client receives progress events.
                await continue_response.wait()
                yield ModelTextDelta(delta=" second")
                yield answer_item("First second")
                yield ModelFinished(reason="stop")
            finally:
                closed = True

        with patch(
            "lp_agent.adapters.bedrock.BedrockClient.stream",
            model_stream,
        ):
            response = self.client.post(self.url, self.data)
            self.assertFalse(response.is_async)
            self.assertEqual(response["Cache-Control"], "no-store")
            stream = iter(response.streaming_content)
            try:
                self.assertEqual(
                    json.loads(next(stream))["payload"]["status"]["state"],
                    "running",
                )
                while True:
                    payload = json.loads(next(stream))["payload"]
                    self.assertNotEqual(payload["type"], "text")
                    if (
                        payload["type"] == "tool"
                        and payload["name"] == "model_response"
                    ):
                        break
                self.assertFalse(closed)
                continue_response.set()
                remaining = [json.loads(chunk) for chunk in stream]
                self.assertEqual(
                    remaining[-1]["payload"]["outcome"]["text"], "First second"
                )
            finally:
                self.close_response(response)
        self.assertTrue(closed)
        self.assertEqual(requests[0][0], self.data["model"])
        self.assertEqual(
            requests[0][1].input[-1].content, self.data["message"]
        )
        self.assertIn(self.data["court"], requests[0][1].instructions)

    def test_response_close_releases_unfinished_model(self):
        closed = False

        async def model_stream(client, request):
            nonlocal closed
            try:
                yield ModelTextDelta(delta="Partial")
                await asyncio.Event().wait()
            finally:
                closed = True

        with patch(
            "lp_agent.adapters.bedrock.BedrockClient.stream",
            model_stream,
        ):
            response = self.client.post(self.url, self.data)
            stream = iter(response.streaming_content)
            try:
                while True:
                    payload = json.loads(next(stream))["payload"]
                    if (
                        payload["type"] == "tool"
                        and payload["name"] == "model_response"
                    ):
                        break
            finally:
                self.close_response(response)
        self.assertTrue(closed)

    def test_model_error_is_shown_without_provider_exception_details(self):
        async def model_stream(client, request):
            yield ModelTextDelta(delta="Partial")
            raise RuntimeError("private provider payload")

        with patch(
            "lp_agent.adapters.bedrock.BedrockClient.stream",
            model_stream,
        ):
            response = self.client.post(self.url, self.data)
            try:
                chunks = [
                    json.loads(chunk) for chunk in response.streaming_content
                ]
            finally:
                self.close_response(response)
        self.assertEqual(chunks[-1]["payload"]["outcome"]["state"], "failed")
        self.assertNotIn("private provider payload", json.dumps(chunks))
        saved = self.client.get(
            reverse(
                "pages:agent_development_conversation",
                kwargs={"conversation_id": chunks[-1]["conversation_id"]},
            )
        )
        self.assertEqual(saved.status_code, 200)
        messages = saved.json()["messages"]
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[-1]["role"], "assistant")
        self.assertEqual(
            messages[-1]["text"],
            chunks[-1]["payload"]["outcome"]["error"]["message"],
        )
        self.assertEqual(messages[-1]["sources"], [])
        self.assertNotIn("private provider payload", json.dumps(messages))
        self.assertNotIn("Partial", json.dumps(messages))

    def consume(self, response):
        try:
            return [json.loads(chunk) for chunk in response.streaming_content]
        finally:
            self.close_response(response)

    def test_provider_failure_codes_and_safe_messages_reach_the_page(self):
        for kind in ("timeout", "unavailable"):
            with self.subTest(kind=kind):

                async def model_stream(client, request, kind=kind):
                    raise ModelProviderError(
                        kind=kind,
                        model=MODEL_CHOICES[0][0],
                        stage="stream",
                        exception_class="ProviderError",
                        status_code=408 if kind == "timeout" else 503,
                        elapsed_seconds=1.25,
                        request_id="provider-request-123",
                    )
                    yield

                with (
                    patch(
                        "lp_agent.adapters.bedrock.BedrockClient.stream",
                        model_stream,
                    ),
                    self.assertLogs("lp_agent.flows.engagement") as logs,
                ):
                    chunks = self.consume(
                        self.client.post(self.url, self.data)
                    )
                outcome = chunks[-1]["payload"]["outcome"]
                self.assertEqual(outcome["state"], "failed")
                self.assertEqual(outcome["error"]["code"], f"model_{kind}")
                self.assertEqual(set(outcome["error"]), {"code", "message"})
                self.assertIn(outcome["run_id"], logs.output[0])
                self.assertNotIn("provider-request-123", json.dumps(chunks))
                saved = self.client.get(
                    reverse(
                        "pages:agent_development_conversation",
                        kwargs={"conversation_id": outcome["conversation_id"]},
                    )
                )
                self.assertEqual(saved.status_code, 200)
                self.assertEqual(
                    saved.json()["messages"][-1]["text"],
                    outcome["error"]["message"],
                )

    def test_static_scope_selection_preserves_original_question_and_reloads(
        self,
    ):
        requests = []

        async def model_stream(client, request):
            if request.instructions.startswith("You review candidate"):
                yield answer_item('{"approved": true, "findings": []}')
            else:
                requests.append(request)
                yield answer_item("I can help with this court matter.")
            yield ModelFinished(reason="stop")

        with patch(
            "lp_agent.adapters.bedrock.BedrockClient.stream", model_stream
        ):
            data = self.data | {
                "court": "",
                "topic": "",
                "message": "What help is available?",
            }
            chunks = self.consume(self.client.post(self.url, data))
            conversation_id = chunks[-1]["conversation_id"]
            self.assertIn(
                "Choose the court", chunks[-1]["payload"]["outcome"]["text"]
            )
            self.assertEqual(requests, [])
            data |= {"conversation_id": conversation_id, "message": "1"}
            chunks = self.consume(self.client.post(self.url, data))
            self.assertIn(
                "Choose the topic", chunks[-1]["payload"]["outcome"]["text"]
            )
            self.assertEqual(requests, [])
            chunks = self.consume(self.client.post(self.url, data))
            self.assertEqual(
                chunks[-1]["payload"]["outcome"]["state"], "completed"
            )
            self.assertEqual(
                requests[0].input[-1].content, "What help is available?"
            )
            url = reverse(
                "pages:agent_development_conversation",
                kwargs={"conversation_id": conversation_id},
            )
            saved = self.client.get(url)
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(len(saved.json()["messages"]), 6)
            self.assertTrue(saved.json()["scope"]["court"])
            chunks = self.consume(
                self.client.post(self.url, data | {"message": "What next?"})
            )
            self.assertEqual(chunks[-1]["conversation_id"], conversation_id)
            self.assertTrue(
                any(
                    isinstance(item, ModelMessage)
                    and message_text(item)
                    == "I can help with this court matter."
                    for item in requests[-1].input
                )
            )
        self.other.groups.add(Group.objects.get(name=DEVELOPERS_GROUP))
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(url).status_code, 404)
