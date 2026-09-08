import asyncio
from dataclasses import replace
from unittest.mock import patch

import pytest

from lp_agent import AgentAccessError, AgentValidationError, LPAgent, RunLimits
from lp_agent.adapters.memory import MemoryConversationStore, MemoryRunStore
from lp_agent.environment import AgentEnvironment, ScopedEnvironment
from lp_agent.types import (
    AccessContext,
    Choice,
    ModelFinished,
    ModelTextDelta,
    ScopeSelection,
)


class ScriptedModel:
    """
    A core-only test model; no provider credentials or framework required.
    """

    def __init__(self, events):
        self.events = events
        self.requests = []
        self.closed = False

    async def stream(self, request):
        self.requests.append(request)
        try:
            for event in self.events:
                if isinstance(event, Exception):
                    raise event
                yield event
        finally:
            self.closed = True


class TestScopes:
    """
    Supply fixed authorized scope and a controlled model to the executor.
    """

    def __init__(self, model):
        self.model = model
        self.bindings = []

    async def courts(self, *, access, topic=None):
        return (Choice(choice_id="court", label="Court"),)

    async def topics(self, *, access, court):
        return (Choice(choice_id="topic", label="Topic"),)

    async def bind(self, *, access, scope):
        self.bindings.append(scope)
        return ScopedEnvironment(
            access=access,
            scope=scope,
            model=self.model,
            corpus=None,
            documents=None,
        )


def environment_for(model):
    conversations = MemoryConversationStore()
    scopes = TestScopes(model)
    return AgentEnvironment(
        access=AccessContext(identity_id="user-1"),
        scope=ScopeSelection(court="court", topic="topic"),
        conversations=conversations,
        runs=MemoryRunStore(conversations),
        catalog=scopes,
        scope_factory=scopes,
    )


def test_direct_result_without_observer_and_independent_submissions():
    async def scenario():
        model = ScriptedModel(
            [
                ModelTextDelta(delta="Hello"),
                ModelTextDelta(delta=" there"),
                ModelFinished(reason="stop"),
            ]
        )
        environment = environment_for(model)
        async with LPAgent(environment=environment) as agent:
            first = await agent.run(message="  First question  ")
            assert (await first.result()).text == "Hello there"
            assert (await first.status()).state == "completed"
            events = [event async for event in first.events()]
            assert [e.payload.type for e in events] == [
                "status",
                "text",
                "text",
                "status",
                "outcome",
            ]
            second = await agent.run(message="Second question")
            await second.result()
            assert first.conversation_id != second.conversation_id
        assert len(environment.scope_factory.bindings) == 1
        assert model.requests[0].messages[-1].text == "  First question  "
        assert len(model.requests[1].messages) == 2
        assert model.requests[1].messages[-1].text == "Second question"
        assert all(request.tools == () for request in model.requests)
        assert model.closed

    asyncio.run(scenario())


def test_first_text_arrives_before_completion_and_closing_releases_model():
    async def scenario():
        blocked = asyncio.Event()
        released = asyncio.Event()

        class SlowModel:
            async def stream(self, request):
                try:
                    yield ModelTextDelta(delta="First")
                    await blocked.wait()
                finally:
                    released.set()

        agent = LPAgent(environment=environment_for(SlowModel()))
        run = await agent.run(message="Hello")
        events = run.events()
        assert (await anext(events)).payload.status.state == "running"
        assert (await anext(events)).payload.delta == "First"
        assert (await run.status()).state == "running"
        await agent.aclose()
        assert released.is_set()
        assert (await run.result()).state == "cancelled"
        await events.aclose()
        with pytest.raises(AgentValidationError, match="closed"):
            await agent.run(message="Again")

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "events,code",
    [
        ([ModelTextDelta(delta="Partial")], "incomplete_response"),
        ([ModelFinished(reason="length")], "incomplete_response"),
        ([RuntimeError("private prompt and credentials")], "model_failed"),
    ],
)
def test_model_failures_are_terminal_and_safe(events, code, caplog):
    async def scenario():
        model = ScriptedModel(events)
        async with LPAgent(environment=environment_for(model)) as agent:
            run = await agent.run(message="private input")
            outcome = await run.result()
            assert outcome.state == "failed"
            assert outcome.error.code == code
            assert "private" not in outcome.model_dump_json()
            assert model.closed

    asyncio.run(scenario())
    assert "private" not in caplog.text


def test_timeout_closes_a_model_that_never_finishes():
    async def scenario():
        closed = asyncio.Event()

        class StuckModel:
            async def stream(self, request):
                try:
                    yield ModelTextDelta(delta="Partial")
                    await asyncio.Event().wait()
                finally:
                    closed.set()

        async with LPAgent(
            environment=environment_for(StuckModel()),
            limits=RunLimits(max_active_seconds=0.01),
        ) as agent:
            run = await agent.run(message="Hello")
            outcome = await asyncio.wait_for(run.result(), timeout=1)
            assert outcome.error.code == "active_time_limit"
            assert closed.is_set()

    asyncio.run(scenario())


def test_cancel_before_task_start_does_not_call_model():
    async def scenario():
        model = ScriptedModel([ModelFinished(reason="stop")])
        agent = LPAgent(environment=environment_for(model))
        run = await agent.run(message="Hello")
        await agent.aclose()
        assert (await run.result()).state == "cancelled"
        assert model.requests == []

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "scope",
    [
        ScopeSelection(),
        ScopeSelection(court="court"),
        ScopeSelection(court="other", topic="topic"),
        ScopeSelection(court="court", topic="other"),
    ],
)
def test_invalid_scope_never_calls_model(scope):
    async def scenario():
        model = ScriptedModel([])
        agent = LPAgent(
            environment=replace(environment_for(model), scope=scope)
        )
        with pytest.raises((AgentValidationError, AgentAccessError)):
            await agent.run(message="Hello")
        assert model.requests == []

    asyncio.run(scenario())


def test_memory_stores_enforce_identity_on_run_reads_and_writes():
    async def scenario():
        environment = environment_for(
            ScriptedModel([ModelFinished(reason="stop")])
        )
        async with LPAgent(environment=environment) as agent:
            run = await agent.run(message="Hello")
            outcome = await run.result()
            status = await run.status()
            checkpoint = await environment.runs.checkpoint(
                access=environment.access,
                run_id=run.run_id,
            )
            intruder = AccessContext(identity_id="user-2")
            with pytest.raises(AgentAccessError):
                await environment.runs.status(
                    access=intruder, run_id=run.run_id
                )
            with pytest.raises(AgentAccessError):
                await environment.runs.commit_checkpoint(
                    access=intruder,
                    checkpoint=checkpoint,
                    status=status,
                    outcome=outcome,
                )

    asyncio.run(scenario())


@pytest.mark.parametrize("stage", ["scope", "conversation", "run"])
def test_close_waits_for_preparation_then_joins_accepted_work(stage):
    async def scenario():
        preparing = asyncio.Event()
        resume = asyncio.Event()
        model_calls = []
        released = []

        class WaitingModel:
            async def stream(self, request):
                model_calls.append(request)
                try:
                    yield ModelTextDelta(delta="Partial")
                    await asyncio.Event().wait()
                finally:
                    released.append(request)

        environment = environment_for(WaitingModel())
        service, method = {
            "scope": (environment.scope_factory, "bind"),
            "conversation": (environment.conversations, "create"),
            "run": (environment.runs, "create"),
        }[stage]
        original = getattr(service, method)

        async def paused(**kwargs):
            preparing.set()
            await resume.wait()
            return await original(**kwargs)

        agent = LPAgent(environment=environment)
        with patch.object(service, method, paused):
            submission = asyncio.create_task(agent.run(message="Hello"))
            await asyncio.wait_for(preparing.wait(), timeout=1)
            closing = asyncio.create_task(agent.aclose())
            await asyncio.sleep(0)
            assert not closing.done()
            after_close = asyncio.create_task(agent.run(message="Too late"))
            resume.set()
            run = await asyncio.wait_for(submission, timeout=1)
            await asyncio.wait_for(closing, timeout=1)
        assert (await run.result()).state == "cancelled"
        assert (await run.status()).state == "cancelled"
        with pytest.raises(AgentValidationError, match="closed"):
            await after_close
        assert released == model_calls
        calls_at_close = len(model_calls)
        await asyncio.sleep(0)
        assert len(model_calls) == calls_at_close
        await agent.aclose()
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


def test_concurrent_closes_join_every_accepted_run():
    async def scenario():
        all_started = asyncio.Event()
        started = []
        released = []

        class WaitingModel:
            async def stream(self, request):
                started.append(request)
                if len(started) == 3:
                    all_started.set()
                try:
                    yield ModelTextDelta(delta="Partial")
                    await asyncio.Event().wait()
                finally:
                    released.append(request)

        agent = LPAgent(environment=environment_for(WaitingModel()))
        runs = [await agent.run(message=str(i)) for i in range(3)]
        await asyncio.wait_for(all_started.wait(), timeout=1)
        await asyncio.wait_for(
            asyncio.gather(agent.aclose(), agent.aclose()), timeout=1
        )
        assert len(released) == 3
        for run in runs:
            assert (await run.result()).state == "cancelled"
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())


def test_close_waits_for_a_terminal_commit_already_in_progress():
    async def scenario():
        committing = asyncio.Event()
        resume = asyncio.Event()
        environment = environment_for(
            ScriptedModel(
                [ModelTextDelta(delta="Done"), ModelFinished(reason="stop")]
            )
        )
        commit = environment.runs.commit_checkpoint

        async def paused(**kwargs):
            if kwargs["outcome"] is not None:
                committing.set()
                await resume.wait()
            await commit(**kwargs)

        agent = LPAgent(environment=environment)
        with patch.object(environment.runs, "commit_checkpoint", paused):
            run = await agent.run(message="Hello")
            await asyncio.wait_for(committing.wait(), timeout=1)
            closing = asyncio.create_task(agent.aclose())
            await asyncio.sleep(0)
            assert not closing.done()
            resume.set()
            await asyncio.wait_for(closing, timeout=1)
        assert (await run.result()).state == "completed"
        assert (await run.status()).state == "completed"
        events = [event async for event in run.events()]
        assert events[-1].payload.outcome.text == "Done"
        assert asyncio.all_tasks() == {asyncio.current_task()}

    asyncio.run(scenario())
