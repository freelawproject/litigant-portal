"""Safe fallback payloads for failed assistant streams, and the events a
healthy tool round emits. All DB-free: the engine's collaborators are patched."""

import json
import uuid
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.urls import reverse

from litigant_portal.agents.base import Agent, ToolOutput
from litigant_portal.app.models import Topic, TopicFlow
from litigant_portal.app.services.chat_engine import chat_stream


class FailingAgent(Agent):
    def generate_system_prompt(self, *, thread_id) -> str:
        return "Test prompt"


def _flow(court="franklin-county-oh"):
    return TopicFlow(
        topic=Topic(slug="eviction", court=court),
        slug="tenant",
        name="Tenant eviction guide",
    )


def _text_chunk(content):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=[])
            )
        ]
    )


def _tool_chunk(*call_ids):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            index=index,
                            id=call_id,
                            function=SimpleNamespace(
                                name="tool", arguments="{}"
                            ),
                        )
                        for index, call_id in enumerate(call_ids)
                    ],
                )
            )
        ]
    )


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

        with patch(
            "litigant_portal.app.services.chat_engine.topic_flow_from_path",
            return_value=_flow(),
        ) as from_path:
            events = self.stream_events()
            # The fallback reads three fields; the content graph stays home.
            from_path.assert_called_once_with("eviction/tenant", graph=False)
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

                with patch(
                    "litigant_portal.app.services.chat_engine.topic_flow_from_path",
                    return_value=None,
                ):
                    events = self.stream_events()
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
            "topic_flow_url_kwargs",
            "reverse",
        ):
            with (
                self.subTest(resolver=resolver),
                patch(
                    "litigant_portal.app.services.chat_engine.topic_flow_from_path",
                    return_value=_flow(),
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

    def test_topic_without_a_court_falls_back_to_home(self):
        self.thread.state = {"active_topic_flow": "eviction/tenant"}
        with patch(
            "litigant_portal.app.services.chat_engine.topic_flow_from_path",
            return_value=_flow(court=""),
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
        text_chunk = _text_chunk("Healthy answer")
        tool_chunk = _tool_chunk("call-1")
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

    def test_tool_round_that_stores_a_fact_announces_it_after_its_responses(
        self,
    ):
        # Two tools in one round, only the first stores something: the
        # announcement comes once, after both responses and the state push,
        # so the panel refetch sees every write from the round.
        with patch(
            "litigant_portal.app.services.chat_engine._execute_tool",
            side_effect=[
                ToolOutput(result="Saved", refresh_system_prompt=True),
                ToolOutput(result="Nothing to save"),
            ],
        ):
            events = self.stream_events(
                completions=[
                    iter([_tool_chunk("call-1", "call-2")]),
                    iter([_text_chunk("Healthy answer")]),
                ]
            )

        self.assertEqual(
            [event["type"] for event in events],
            [
                "thread",
                "state",
                "tool_call",
                "tool_response",
                "tool_call",
                "tool_response",
                "state",
                "briefcase_changed",
                "content_delta",
                "done",
            ],
        )
        self.assertEqual(events[7], {"type": "briefcase_changed"})

    def test_tool_round_that_stores_nothing_announces_no_briefcase_change(
        self,
    ):
        with patch(
            "litigant_portal.app.services.chat_engine._execute_tool",
            return_value=ToolOutput(result="Tool finished"),
        ):
            events = self.stream_events(
                completions=[
                    iter([_tool_chunk("call-1")]),
                    iter([_text_chunk("Healthy answer")]),
                ]
            )

        self.assertNotIn(
            "briefcase_changed", [event["type"] for event in events]
        )
