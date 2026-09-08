"""
Provider adapter checks using synthetic SDK streams, without Django.
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch

import pytest
from litellm.types.utils import ModelResponseStream

from lp_agent import LPAgent
from lp_agent.adapters.bedrock import MODEL_CHOICES, BedrockClient
from lp_agent.adapters.environment import create_environment
from lp_agent.tests.test_environment_factory import environment_options
from lp_agent.types import ModelMessage, ModelRequest


def test_stream_normalizes_text_and_finish_and_closes_provider():
    async def scenario():
        closed = False

        async def provider():
            nonlocal closed
            try:
                yield ModelResponseStream(
                    choices=[{"delta": {"content": "First"}}]
                )
                yield ModelResponseStream(
                    choices=[
                        {
                            "delta": {"content": " second"},
                            "finish_reason": "stop",
                        }
                    ],
                )
            finally:
                closed = True

        completion = AsyncMock(return_value=provider())
        request = ModelRequest(
            messages=(ModelMessage(role="user", text="Hello"),)
        )
        with patch("litellm.acompletion", completion):
            events = [
                event
                async for event in BedrockClient(
                    MODEL_CHOICES[0][0], api_key="supplied-test-key"
                ).stream(request)
            ]
        assert [event.type for event in events] == ["text", "text", "finished"]
        assert events[-1].reason == "stop"
        assert closed
        args = completion.call_args.kwargs
        assert args["model"] == MODEL_CHOICES[0][0]
        assert args["messages"] == [{"role": "user", "content": "Hello"}]
        assert args["stream"]
        assert args["num_retries"] == 0
        assert not args["caching"]
        assert "tools" not in args
        assert args["api_key"] == "supplied-test-key"

    asyncio.run(scenario())


def test_close_after_one_delta_releases_provider():
    async def scenario():
        closed = False

        async def provider():
            nonlocal closed
            try:
                yield ModelResponseStream(
                    choices=[{"delta": {"content": "First"}}]
                )
                await asyncio.Event().wait()
            finally:
                closed = True

        with patch("litellm.acompletion", AsyncMock(return_value=provider())):
            stream = BedrockClient(
                MODEL_CHOICES[0][0], api_key="supplied-test-key"
            ).stream(ModelRequest(messages=()))
            assert (await anext(stream)).delta == "First"
            await stream.aclose()
        assert closed

    asyncio.run(scenario())


@pytest.mark.parametrize("reason", ["length", "content_filter", "tool_calls"])
def test_incomplete_finish_is_preserved(reason):
    async def scenario():
        async def provider():
            yield ModelResponseStream(
                choices=[{"delta": {}, "finish_reason": reason}],
            )

        with patch("litellm.acompletion", AsyncMock(return_value=provider())):
            events = [
                event
                async for event in BedrockClient(
                    MODEL_CHOICES[0][0], api_key="supplied-test-key"
                ).stream(ModelRequest(messages=()))
            ]
        assert events[-1].reason == reason

    asyncio.run(scenario())


def test_supplied_key_reaches_provider_but_not_run_data_or_events(monkeypatch):
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "unused-environment-key")
    environment = create_environment(**environment_options())

    async def provider():
        yield ModelResponseStream(
            choices=[{"delta": {"content": "Hello"}, "finish_reason": "stop"}]
        )

    completion = AsyncMock(return_value=provider())
    with (
        patch("litellm.acompletion", completion),
        patch.object(
            environment.runs, "create", wraps=environment.runs.create
        ) as create,
    ):
        events = [
            json.loads(line)
            for line in LPAgent(environment=environment).stream(
                message="Hello"
            )
        ]
    assert completion.call_args.kwargs["api_key"] == "test-only-key"
    configuration = create.call_args.kwargs["configuration"].model_dump_json()
    checkpoint = asyncio.run(
        environment.runs.checkpoint(
            access=environment.access, run_id=events[0]["run_id"]
        )
    )
    serialized = (
        json.dumps(events) + configuration + checkpoint.model_dump_json()
    )
    assert events[-1]["payload"]["outcome"]["state"] == "completed"
    assert "test-only-key" not in serialized
    assert "api_key" not in serialized
