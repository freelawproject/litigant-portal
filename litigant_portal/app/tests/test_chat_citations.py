"""Postgres tests: the engine records cited ids a thread never supplied.

The LLM is mocked the way test_prompt_artifacts does it; the agent here
has a LoadTopicFlow-named tool so a flow result can enter the history.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import TestCase

from litigant_portal.agents.base import Agent, Tool, ToolOutput
from litigant_portal.app.models import ChatMessage, ChatThread, UserIdentity
from litigant_portal.app.services import chat_engine as engine
from litigant_portal.app.services.chat_engine import chat_stream

MODEL = "gpt-5-mini"
FLOW_RESULT = (
    "## Filing fee [source:adult-name-change/standard/filing_fee]\n$160."
)


class LoadTopicFlow(Tool):
    """Stand-in for the real tool: same name, canned flow content."""

    def __call__(self, *, thread_id) -> ToolOutput:
        return ToolOutput(result=FLOW_RESULT)


class CitingAgent(Agent):
    tools = [LoadTopicFlow]

    def generate_system_prompt(self, *, thread_id) -> str:
        return "### Court contacts\n- [source:court/clerk] Clerk of Court"


def _chunk(*, content=None, tool_calls=None):
    return SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content, tool_calls=tool_calls or []
                )
            )
        ],
    )


def _tool_call_chunk(name):
    return _chunk(
        tool_calls=[
            SimpleNamespace(
                index=0,
                id="call-1",
                function=SimpleNamespace(name=name, arguments="{}"),
            )
        ]
    )


@pytest.mark.postgres
class UnknownCitationTests(TestCase):
    def setUp(self):
        identity = UserIdentity.objects.create(session_key="citations")
        self.thread = ChatThread.objects.create(
            identity=identity,
            thread_type="test_agent",
            description="Existing description",
        )
        self.identity = identity

    def _stream(self, completions):
        with (
            patch.object(
                engine.litellm, "completion", side_effect=completions
            ),
            patch.object(engine.litellm, "token_counter", return_value=0),
        ):
            response = chat_stream(
                identity=self.identity,
                message="Help me.",
                agent_class=CitingAgent,
                thread_type="test_agent",
                model=MODEL,
                thread_id=str(self.thread.id),
            )
            list(response.streaming_content)

    def _final_assistant(self):
        return [
            m
            for m in ChatMessage.objects.filter(thread=self.thread).order_by(
                "created_at"
            )
            if m.data["role"] == "assistant"
        ][-1]

    def test_an_id_the_thread_never_saw_is_stored_and_logged(self):
        with self.assertLogs(engine.logger, level="WARNING") as logs:
            self._stream(
                [iter([_chunk(content="Fee is $160 [source:court/ghost].")])]
            )
        self.assertEqual(
            self._final_assistant().data["unknown_citations"], ["court/ghost"]
        )
        (line,) = logs.output
        self.assertIn("['court/ghost']", line)
        self.assertIn(str(self.thread.id), line)

    def test_ids_from_the_prompt_and_a_loaded_flow_are_known(self):
        self._stream(
            [
                iter([_tool_call_chunk("LoadTopicFlow")]),
                iter(
                    [
                        _chunk(
                            content=(
                                "Fee is $160 "
                                "[source:adult-name-change/standard/filing_fee]"
                                " and the clerk can help [source:court/clerk]."
                            )
                        )
                    ]
                ),
            ]
        )
        self.assertNotIn("unknown_citations", self._final_assistant().data)

    def test_a_flow_loaded_in_an_earlier_turn_still_counts(self):
        self._stream([iter([_tool_call_chunk("LoadTopicFlow")]), iter([])])
        self._stream(
            [
                iter(
                    [
                        _chunk(
                            content=(
                                "[source:adult-name-change/standard/filing_fee]"
                            )
                        )
                    ]
                )
            ]
        )
        self.assertNotIn("unknown_citations", self._final_assistant().data)
