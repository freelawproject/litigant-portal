"""The engine runs Agent.prepare_thread once per user message, before the
first model call."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.test import SimpleTestCase, TestCase

from litigant_portal.agents.base import Agent
from litigant_portal.app.models import ChatThread, UserIdentity
from litigant_portal.app.services.chat_engine import chat_stream


class PreparingAgent(Agent):
    events: list = []

    def prepare_thread(self, *, thread_id) -> None:
        type(self).events.append("prepare")

    def generate_system_prompt(self, *, thread_id) -> str:
        type(self).events.append("prompt")
        return "Prepared prompt"


def _chunk(content):
    return SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(content=content, tool_calls=[])
            )
        ],
    )


class PrepareThreadDefaultTests(SimpleTestCase):
    def test_base_hook_is_a_noop(self):
        self.assertIsNone(Agent().prepare_thread(thread_id="ignored"))


@pytest.mark.postgres
class PrepareThreadEngineTests(TestCase):
    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="prep")
        self.thread = ChatThread.objects.create(
            identity=self.identity,
            thread_type="test_agent",
            description="Existing description",
        )
        PreparingAgent.events = []

    def test_runs_once_before_the_first_prompt_build(self):
        with (
            patch(
                "litigant_portal.app.services.chat_engine.litellm.completion",
                return_value=iter([_chunk("Answer.")]),
            ),
            patch(
                "litigant_portal.app.services.chat_engine.litellm.token_counter",
                return_value=0,
            ),
        ):
            response = chat_stream(
                identity=self.identity,
                message="Hello.",
                agent_class=PreparingAgent,
                thread_type="test_agent",
                model="gpt-5-mini",
                thread_id=str(self.thread.id),
            )
            list(response.streaming_content)

        self.assertEqual(PreparingAgent.events.count("prepare"), 1)
        self.assertEqual(PreparingAgent.events[0], "prepare")
        self.assertIn("prompt", PreparingAgent.events)
