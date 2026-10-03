"""Safe fallback payloads for failed assistant streams."""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from django.urls import reverse

from litigant_portal.agents.base import Agent
from litigant_portal.app.models import TopicFlow
from litigant_portal.app.services.chat_engine import chat_stream


class FailingAgent(Agent):
    def generate_system_prompt(self, *, thread_id) -> str:
        return "Test prompt"


class ChatStreamFallbackTests(SimpleTestCase):
    def setUp(self):
        self.identity = object()
        self.thread = SimpleNamespace(
            id=uuid.uuid4(),
            state={},
            description="Existing description",
        )

    def stream_error(self):
        with (
            patch(
                "litigant_portal.app.services.chat_engine.litellm.completion",
                side_effect=RuntimeError("secret-provider-detail"),
            ),
            patch(
                "litigant_portal.app.services.chat_engine.litellm.token_counter",
                return_value=0,
            ),
            patch(
                "litigant_portal.app.services.chat_engine._resolve_thread",
                return_value=self.thread,
            ),
            patch(
                "litigant_portal.app.services.chat_engine.chat_message_create"
            ),
            patch(
                "litigant_portal.app.services.chat_engine.chat_message_list",
                return_value=[
                    SimpleNamespace(
                        data={"role": "user", "content": "Please help."}
                    )
                ],
            ),
            patch(
                "litigant_portal.app.services.chat_engine.prompt_artifact_get_or_create",
                return_value=object(),
            ),
        ):
            response = chat_stream(
                identity=self.identity,
                message="Please help.",
                agent_class=FailingAgent,
                thread_type="test_agent",
                model="test-model",
                thread_id=str(self.thread.id),
            )
            return [
                json.loads(
                    frame.decode("utf-8").removeprefix("data: ").strip()
                )
                for frame in response.streaming_content
            ]

    def test_active_valid_flow_gets_guided_fallback_and_safe_error(self):
        self.thread.state = {"active_topic_flow": "eviction/tenant"}
        flow = SimpleNamespace(
            topic=SimpleNamespace(slug="eviction"),
            slug="tenant",
            name="Tenant eviction guide",
        )
        track = {
            "court": "franklin-county-oh",
            "topic": "eviction",
            "role": "tenant",
        }

        with (
            patch(
                "litigant_portal.app.services.chat_engine.TopicFlow.objects.filter"
            ) as flow_filter,
            patch(
                "litigant_portal.app.services.chat_engine.registry.tracks_for",
                return_value=[track],
            ),
        ):
            flow_first = flow_filter.return_value.select_related.return_value.first
            flow_first.return_value = flow
            events = self.stream_error()
            flow_filter.assert_called_once_with(
                topic__slug="eviction", slug="tenant", enabled=True
            )
        error = next(event for event in events if event["type"] == "error")

        self.assertEqual(
            error["fallback_url"],
            reverse(
                "pages:topic_flow",
                kwargs={
                    "court": "franklin-county-oh",
                    "topic": "eviction",
                    "role": "tenant",
                },
            ),
        )
        self.assertEqual(
            error["fallback_label"],
            "Tenant eviction guide",
        )
        self.assertIn("temporarily unavailable", error["message"])
        self.assertNotIn("error", error)
        self.assertNotIn("secret-provider-detail", json.dumps(events))
        self.assertEqual(events[-1], {"type": "done"})

    def test_no_active_or_invalid_flow_falls_back_to_home(self):
        for state in ({}, {"active_topic_flow": "bad/flow/path"}):
            with self.subTest(state=state):
                self.thread.state = state

                with patch(
                    "litigant_portal.app.services.chat_engine.TopicFlow.objects.filter"
                ) as flow_filter:
                    flow_first = (
                        flow_filter.return_value.select_related.return_value.first
                    )
                    flow_first.return_value = None
                    events = self.stream_error()
                error = next(
                    event for event in events if event["type"] == "error"
                )
                self.assertEqual(error["fallback_url"], "/")
                self.assertEqual(
                    error["fallback_label"], "Browse the help topics"
                )
                self.assertNotIn("secret-provider-detail", json.dumps(events))

    def test_resolution_failure_keeps_safe_home_error_and_hides_both_exceptions(self):
        self.thread.state = {"active_topic_flow": "eviction/tenant"}
        with patch(
            "litigant_portal.app.services.chat_engine.TopicFlow.objects.filter",
            side_effect=RuntimeError("secret-resolution-detail"),
        ):
            events = self.stream_error()

        error = next(event for event in events if event["type"] == "error")
        self.assertEqual(error["fallback_url"], "/")
        self.assertEqual(error["fallback_label"], "Browse the help topics")
        payload = json.dumps(events)
        self.assertNotIn("secret-provider-detail", payload)
        self.assertNotIn("secret-resolution-detail", payload)
