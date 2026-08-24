"""Tests for capturing the instruction state behind assistant messages."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import SimpleTestCase, TestCase

from litigant_portal.agents.base import Agent, Tool, ToolOutput
from litigant_portal.app.models import (
    ChatMessage,
    ChatThread,
    PromptArtifact,
    UserIdentity,
)
from litigant_portal.app.services.chat_engine import (
    chat_message_create,
    chat_message_inject_hidden,
    chat_message_inject_meta,
    chat_stream,
    prompt_artifact_content_hash,
    prompt_artifact_get_or_create,
)

MODEL = "gpt-5-mini"


def _schema(*, description: str = "Look something up") -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query", "limit"],
                },
            },
        }
    ]


class PromptArtifactHashTests(SimpleTestCase):
    def test_hash_is_stable_across_object_key_order(self):
        schemas = _schema()
        reordered = [
            {
                "function": {
                    "parameters": {
                        "required": ["query", "limit"],
                        "properties": {
                            "limit": {"type": "integer"},
                            "query": {"type": "string"},
                        },
                        "type": "object",
                    },
                    "description": "Look something up",
                    "name": "lookup",
                },
                "type": "function",
            }
        ]

        first = prompt_artifact_content_hash(
            system_prompt="Be helpful.", tool_schemas=schemas
        )
        second = prompt_artifact_content_hash(
            system_prompt="Be helpful.", tool_schemas=reordered
        )

        self.assertEqual(first, second)

    def test_hash_changes_when_prompt_changes(self):
        first = prompt_artifact_content_hash(
            system_prompt="Be helpful.", tool_schemas=_schema()
        )
        second = prompt_artifact_content_hash(
            system_prompt="Be precise.", tool_schemas=_schema()
        )

        self.assertNotEqual(first, second)

    def test_hash_changes_when_tool_schemas_change(self):
        first = prompt_artifact_content_hash(
            system_prompt="Be helpful.", tool_schemas=_schema()
        )
        second = prompt_artifact_content_hash(
            system_prompt="Be helpful.",
            tool_schemas=_schema(description="Search court records"),
        )

        self.assertNotEqual(first, second)

    def test_hash_preserves_schema_array_order(self):
        schemas = _schema() + [
            {
                "type": "function",
                "function": {
                    "name": "summarize",
                    "description": "Summarize a result",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        forward = prompt_artifact_content_hash(
            system_prompt="Be helpful.", tool_schemas=schemas
        )
        reversed_order = prompt_artifact_content_hash(
            system_prompt="Be helpful.", tool_schemas=list(reversed(schemas))
        )

        self.assertNotEqual(forward, reversed_order)


@pytest.mark.postgres
class PromptArtifactDeduplicationTests(TestCase):
    def test_reuses_artifact_for_identical_instruction_state(self):
        first = prompt_artifact_get_or_create(
            system_prompt="Be helpful.", tool_schemas=_schema()
        )
        second = prompt_artifact_get_or_create(
            system_prompt="Be helpful.", tool_schemas=_schema()
        )

        self.assertEqual(first, second)
        self.assertEqual(PromptArtifact.objects.count(), 1)


class RefreshPrompt(Tool):
    """Refresh the prompt before the next model call."""

    def __call__(self, *, thread_id) -> ToolOutput:
        return ToolOutput(
            result="Prompt refreshed.", refresh_system_prompt=True
        )


class RefreshingAgent(Agent):
    tools = [RefreshPrompt]
    schema_reads = 0

    def __init__(self):
        self.prompt_number = 0

    def generate_system_prompt(self, *, thread_id) -> str:
        self.prompt_number += 1
        return f"System prompt {self.prompt_number}"

    @property
    def tool_schemas(self) -> list[dict] | None:
        type(self).schema_reads += 1
        return super().tool_schemas


class NoToolsAgent(Agent):
    def generate_system_prompt(self, *, thread_id) -> str:
        return "System prompt without tools"


def _chunk(*, content=None, tool_calls=None):
    return SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls or [],
                )
            )
        ],
    )


@pytest.mark.postgres
class PromptArtifactCaptureTests(TestCase):
    def setUp(self):
        self.identity = UserIdentity.objects.create(
            session_key="prompt-capture"
        )
        self.thread = ChatThread.objects.create(
            identity=self.identity,
            thread_type="test_agent",
            description="Existing description",
        )
        RefreshingAgent.schema_reads = 0

    def test_no_tools_request_links_artifact_with_empty_schema_snapshot(self):
        with (
            patch(
                "litigant_portal.app.services.chat_engine.litellm.completion",
                return_value=iter([_chunk(content="No-tools answer.")]),
            ) as completion,
            patch(
                "litigant_portal.app.services.chat_engine.litellm.token_counter",
                return_value=0,
            ),
        ):
            response = chat_stream(
                identity=self.identity,
                message="Help me without tools.",
                agent_class=NoToolsAgent,
                thread_type="test_agent",
                model=MODEL,
                thread_id=str(self.thread.id),
            )
            list(response.streaming_content)

        completion.assert_called_once()
        self.assertNotIn("tools", completion.call_args.kwargs)
        assistant = next(
            message
            for message in ChatMessage.objects.filter(thread=self.thread)
            if message.data["role"] == "assistant"
        )
        self.assertIsNotNone(assistant.prompt_artifact)
        self.assertEqual(assistant.prompt_artifact.tool_schemas, [])

    def test_non_model_messages_leave_prompt_artifact_null(self):
        with patch(
            "litigant_portal.app.services.chat_engine.litellm.token_counter",
            return_value=0,
        ):
            user = chat_message_create(
                thread_id=self.thread.id,
                data={"role": "user", "content": "Question"},
                model=MODEL,
            )
            tool = chat_message_create(
                thread_id=self.thread.id,
                data={
                    "role": "tool",
                    "tool_call_id": "call-1",
                    "name": "RefreshPrompt",
                    "content": "Result",
                },
                model=MODEL,
            )
            hidden = chat_message_inject_hidden(
                thread_id=self.thread.id,
                content="Hidden context",
                model=MODEL,
            )
            meta = chat_message_inject_meta(
                thread_id=self.thread.id,
                kind="accounting",
                model=MODEL,
            )

        for message in (user, tool, hidden, meta):
            self.assertIsNone(message.prompt_artifact)

    def test_links_each_assistant_turn_to_its_exact_instruction_state(self):
        tool_call = SimpleNamespace(
            index=0,
            id="call-1",
            function=SimpleNamespace(
                name="RefreshPrompt",
                arguments="{}",
            ),
        )
        completions = [
            iter([_chunk(tool_calls=[tool_call])]),
            iter([_chunk(content="Final answer.")]),
        ]

        with (
            patch(
                "litigant_portal.app.services.chat_engine.litellm.completion",
                side_effect=completions,
            ) as completion,
            patch(
                "litigant_portal.app.services.chat_engine.litellm.token_counter",
                return_value=0,
            ),
        ):
            response = chat_stream(
                identity=self.identity,
                message="Help me.",
                agent_class=RefreshingAgent,
                thread_type="test_agent",
                model=MODEL,
                thread_id=str(self.thread.id),
            )
            list(response.streaming_content)

        messages = list(
            ChatMessage.objects.filter(thread=self.thread)
            .select_related("prompt_artifact")
            .order_by("created_at")
        )
        self.assertEqual(
            [message.data["role"] for message in messages],
            ["user", "assistant", "tool", "assistant"],
        )
        user_message = next(
            message for message in messages if message.data["role"] == "user"
        )
        tool_message = next(
            message for message in messages if message.data["role"] == "tool"
        )
        tool_call_assistant = next(
            message
            for message in messages
            if message.data["role"] == "assistant"
            and message.data.get("tool_calls")
        )
        final_assistant = next(
            message
            for message in messages
            if message.data["role"] == "assistant"
            and message.data.get("content") == "Final answer."
        )

        self.assertIsNone(user_message.prompt_artifact)
        self.assertIsNone(tool_message.prompt_artifact)
        self.assertEqual(tool_call_assistant.data["content"], "")
        self.assertIsNotNone(tool_call_assistant.prompt_artifact)
        self.assertIsNotNone(final_assistant.prompt_artifact)
        self.assertNotEqual(
            tool_call_assistant.prompt_artifact_id,
            final_assistant.prompt_artifact_id,
        )
        self.assertEqual(
            tool_call_assistant.prompt_artifact.system_prompt,
            "System prompt 1",
        )
        self.assertEqual(
            final_assistant.prompt_artifact.system_prompt,
            "System prompt 2",
        )

        first_tools = completion.call_args_list[0].kwargs["tools"]
        second_tools = completion.call_args_list[1].kwargs["tools"]
        self.assertEqual(
            tool_call_assistant.prompt_artifact.tool_schemas, first_tools
        )
        self.assertEqual(
            final_assistant.prompt_artifact.tool_schemas, second_tools
        )
        self.assertEqual(RefreshingAgent.schema_reads, 2)
        self.assertEqual(PromptArtifact.objects.count(), 2)
