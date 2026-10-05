"""Safe fallback payloads for failed assistant streams."""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.urls import reverse

from litigant_portal.agents.base import Agent, ToolOutput
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
            refresh_from_db=Mock(),
            save=Mock(),
        )

    def stream_events(self, completions=None):
        with (
            patch(
                "litigant_portal.app.services.chat_engine.litellm.completion",
                side_effect=(
                    completions
                    if completions is not None
                    else RuntimeError("secret-provider-detail")
                ),
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
            ) as create_message,
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
            events = [
                json.loads(
                    frame.decode("utf-8").removeprefix("data: ").strip()
                )
                for frame in response.streaming_content
            ]
            self.persisted_messages = [
                call.kwargs["data"] for call in create_message.call_args_list
            ]
            return events

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
                "litigant_portal.app.services.chat_engine.topic_flow_from_path",
                return_value=flow,
            ) as from_path,
            patch(
                "litigant_portal.app.services.chat_engine.topic_flow_track_find",
                return_value=track,
            ) as track_find,
        ):
            events = self.stream_events()
            from_path.assert_called_once_with("eviction/tenant")
            track_find.assert_called_once_with(flow)
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
        self.assertEqual(
            error["message"],
            "The assistant is temporarily unavailable. You can continue "
            "with the step-by-step guide instead.",
        )
        self.assertNotIn("error", error)
        self.assertNotIn("secret-provider-detail", json.dumps(events))
        self.assertEqual(events[-1], {"type": "done"})

    def test_no_active_or_invalid_flow_falls_back_to_home(self):
        for state in (
            {},
            {"active_topic_flow": None},
            {"active_topic_flow": "bad/flow/path"},
            {"active_topic_flow": "stale/flow"},
        ):
            with self.subTest(state=state):
                self.thread.state = state

                with (
                    patch(
                        "litigant_portal.app.services.chat_engine.topic_flow_from_path",
                        return_value=None,
                    ),
                    patch(
                        "litigant_portal.app.services.chat_engine.topic_flow_track_find"
                    ) as track_find,
                ):
                    events = self.stream_events()
                    track_find.assert_not_called()
                error = next(
                    event for event in events if event["type"] == "error"
                )
                self.assertEqual(error["fallback_url"], "/")
                self.assertEqual(
                    error["fallback_label"], "Browse the help topics"
                )
                self.assertEqual(
                    error["message"],
                    "The assistant is temporarily unavailable. You can "
                    "browse the help topics instead.",
                )
                self.assertNotIn("secret-provider-detail", json.dumps(events))

    def test_resolution_failure_keeps_safe_home_error_and_hides_both_exceptions(
        self,
    ):
        self.thread.state = {"active_topic_flow": "eviction/tenant"}
        for resolver in (
            "topic_flow_from_path",
            "topic_flow_track_find",
            "reverse",
        ):
            with (
                self.subTest(resolver=resolver),
                patch(
                    "litigant_portal.app.services.chat_engine.topic_flow_from_path",
                    return_value=SimpleNamespace(name="Guide"),
                ),
                patch(
                    "litigant_portal.app.services.chat_engine.topic_flow_track_find",
                    return_value={
                        "court": "court",
                        "topic": "topic",
                        "role": "role",
                    },
                ),
                patch(
                    f"litigant_portal.app.services.chat_engine.{resolver}",
                    side_effect=RuntimeError("secret-resolution-detail"),
                ),
            ):
                events = self.stream_events()

                error = next(
                    event for event in events if event["type"] == "error"
                )
                self.assertEqual(error["fallback_url"], "/")
                self.assertEqual(
                    error["fallback_label"], "Browse the help topics"
                )
                self.assertIn("browse the help topics", error["message"])
                payload = json.dumps(events)
                self.assertNotIn("secret-provider-detail", payload)
                self.assertNotIn("secret-resolution-detail", payload)

    def test_unmatched_track_falls_back_to_home(self):
        self.thread.state = {"active_topic_flow": "eviction/tenant"}
        with (
            patch(
                "litigant_portal.app.services.chat_engine.topic_flow_from_path",
                return_value=SimpleNamespace(name="Guide"),
            ),
            patch(
                "litigant_portal.app.services.chat_engine.topic_flow_track_find",
                return_value=None,
            ),
        ):
            events = self.stream_events()

        error = next(event for event in events if event["type"] == "error")
        self.assertEqual(error["fallback_url"], "/")
        self.assertEqual(error["fallback_label"], "Browse the help topics")
        self.assertIn("browse the help topics", error["message"])

    def test_empty_model_stream_emits_fallback_without_empty_assistant_save(
        self,
    ):
        empty_delta = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content=None, tool_calls=[])
                )
            ]
        )
        for chunks in (
            [],
            [SimpleNamespace(choices=[])],
            [empty_delta],
        ):
            with self.subTest(chunks=chunks):
                events = self.stream_events(completions=[iter(chunks)])

                self.assertEqual(
                    [event["type"] for event in events],
                    ["thread", "state", "error", "done"],
                )
                error = events[-2]
                self.assertEqual(error["fallback_url"], "/")
                self.assertEqual(
                    error["fallback_label"], "Browse the help topics"
                )
                self.assertIn("browse the help topics", error["message"])
                self.assertEqual(
                    self.persisted_messages,
                    [{"role": "user", "content": "Please help."}],
                )
                self.thread.save.assert_not_called()

    def test_midstream_provider_failure_preserves_text_and_emits_safe_fallback(
        self,
    ):
        def chunks():
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content="Partial answer", tool_calls=[]
                        )
                    )
                ]
            )
            raise RuntimeError("secret-provider-detail")

        events = self.stream_events(completions=[chunks()])

        self.assertEqual(
            [event["type"] for event in events],
            ["thread", "state", "content_delta", "error", "done"],
        )
        self.assertEqual(events[2]["content"], "Partial answer")
        self.assertEqual(events[-2]["fallback_url"], "/")
        self.assertNotIn("secret-provider-detail", json.dumps(events))
        self.assertEqual(
            self.persisted_messages,
            [{"role": "user", "content": "Please help."}],
        )

    def test_normal_text_and_tool_turns_still_complete(self):
        text_chunk = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content="Healthy answer", tool_calls=[]
                    )
                )
            ]
        )
        tool_chunk = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None,
                        tool_calls=[
                            SimpleNamespace(
                                index=0,
                                id="call-1",
                                function=SimpleNamespace(
                                    name="tool", arguments="{}"
                                ),
                            )
                        ],
                    )
                )
            ]
        )
        for with_tool in (False, True):
            with (
                self.subTest(with_tool=with_tool),
                patch(
                    "litigant_portal.app.services.chat_engine._execute_tool",
                    return_value=ToolOutput(result="Tool finished"),
                ),
            ):
                completions = [iter([text_chunk])]
                if with_tool:
                    completions.insert(0, iter([tool_chunk]))
                events = self.stream_events(completions=completions)

                self.assertNotIn("error", [event["type"] for event in events])
                self.assertEqual(events[-1], {"type": "done"})
                self.assertIn(
                    {"type": "content_delta", "content": "Healthy answer"},
                    events,
                )
                self.assertEqual(
                    self.persisted_messages[-1],
                    {"role": "assistant", "content": "Healthy answer"},
                )
                if with_tool:
                    self.assertEqual(
                        [event["type"] for event in events],
                        [
                            "thread",
                            "state",
                            "tool_call",
                            "tool_response",
                            "state",
                            "content_delta",
                            "done",
                        ],
                    )
                self.thread.save.assert_called_with(
                    update_fields=["updated_at"]
                )
                self.thread.refresh_from_db.assert_called_with(
                    fields=["state"]
                )
