import asyncio
import json
from dataclasses import replace
from unittest.mock import patch

import pytest

from lp_agent import AgentStorageError, AgentValidationError, LPAgent
from lp_agent.tests.helpers import (
    ScriptedModel,
    answer_item,
    environment_for,
)
from lp_agent.types import ModelFinished, ModelTextDelta, ScopeSelection


def test_stream_exhaustion_closes_model_agent_and_own_event_loop():
    loops = []

    class Model:
        async def stream(self, request):
            loops.append(asyncio.get_running_loop())
            yield ModelTextDelta(delta="Hello")
            yield answer_item("Hello")
            yield ModelFinished(reason="stop")

    agent = LPAgent(environment=environment_for(Model()))
    events = [json.loads(line) for line in agent.stream(message="Hello")]
    assert events[-1]["payload"]["outcome"]["text"] == "Hello"
    assert loops[0].is_closed()
    with pytest.raises(AgentValidationError):
        asyncio.run(agent.run(message="Again"))


def test_stream_close_before_iteration_prevents_acceptance():
    model = ScriptedModel([])
    agent = LPAgent(environment=environment_for(model))
    stream = agent.stream(message="Hello")
    stream.close()
    stream.close()
    assert list(stream) == []
    assert model.requests == []
    with pytest.raises(AgentValidationError):
        asyncio.run(agent.run(message="Again"))


def test_stream_context_closes_in_progress_model_and_loop():
    loops = []
    closed = []

    class Model:
        async def stream(self, request):
            loops.append(asyncio.get_running_loop())
            try:
                yield ModelTextDelta(delta="Partial")
                await asyncio.Event().wait()
            finally:
                closed.append(True)

    agent = LPAgent(environment=environment_for(Model()))
    with agent.stream(message="Hello") as stream:
        next(stream)
        assert json.loads(next(stream))["payload"]["delta"] == "Partial"
        with pytest.raises(AgentValidationError, match="unused"):
            agent.stream(message="Second consumer")
        with pytest.raises(AgentValidationError, match="owns"):
            asyncio.run(agent.run(message="Mixed usage"))
    assert closed == [True]
    assert loops[0].is_closed()


def test_stream_rejects_an_instance_with_previously_accepted_work():
    async def scenario():
        async with LPAgent(
            environment=environment_for(ScriptedModel([]))
        ) as agent:
            await agent.run(message="Hello")
            with pytest.raises(AgentValidationError, match="unused"):
                agent.stream(message="Switch modes")

    asyncio.run(scenario())


def test_stream_admission_errors_are_encoded_and_close_the_agent():
    model = ScriptedModel([])
    agent = LPAgent(
        environment=replace(environment_for(model), scope=ScopeSelection())
    )
    events = [json.loads(line) for line in agent.stream(message="Hello")]
    assert events == [{"error": "Select a court and topic before sending."}]
    assert model.requests == []
    with pytest.raises(AgentValidationError):
        asyncio.run(agent.run(message="Again"))


def test_async_caller_cannot_claim_a_synchronous_stream():
    async def scenario():
        async with LPAgent(
            environment=environment_for(ScriptedModel([]))
        ) as agent:
            with pytest.raises(AgentValidationError, match="async caller"):
                agent.stream(message="Hello")
            run = await agent.run(message="Use the async interface")
            await run.result()

    asyncio.run(scenario())


def test_provider_failure_is_safe_and_releases_the_owned_loop(caplog):
    loops = []

    class Model:
        async def stream(self, request):
            loops.append(asyncio.get_running_loop())
            yield ModelTextDelta(delta="Partial")
            raise RuntimeError("private provider payload")

    agent = LPAgent(environment=environment_for(Model()))
    events = list(agent.stream(message="Hello"))
    assert json.loads(events[-1])["payload"]["outcome"]["state"] == "failed"
    assert "private provider payload" not in "".join(events) + caplog.text
    assert loops[0].is_closed()


@pytest.mark.parametrize("early_close", [False, True])
def test_terminal_checkpoint_failure_is_safe_and_releases_the_loop(
    early_close, caplog
):
    loops = []

    class Model:
        async def stream(self, request):
            loops.append(asyncio.get_running_loop())
            yield answer_item("Done")
            yield ModelFinished(reason="stop")

    environment = environment_for(Model())
    commit = environment.runs.commit_checkpoint

    async def failing_commit(**kwargs):
        if kwargs["outcome"] is not None:
            raise RuntimeError("private storage payload")
        await commit(**kwargs)

    with patch.object(environment.runs, "commit_checkpoint", failing_commit):
        stream = LPAgent(environment=environment).stream(message="Hello")
        first = json.loads(next(stream))
        assert first["payload"]["status"]["state"] == "running"
        if early_close:
            with pytest.raises(
                AgentStorageError, match="Unable to save the run state"
            ):
                stream.close()
        else:
            assert [json.loads(line) for line in stream] == [
                {"error": "Unable to save the run state. Please try again."}
            ]
        assert list(stream) == []
        stream.close()
    assert loops[0].is_closed()
    assert "private" not in caplog.text
