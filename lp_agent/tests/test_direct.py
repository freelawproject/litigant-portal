import asyncio
import hashlib
import json
from dataclasses import replace
from unittest.mock import patch

import pytest
from pydantic import TypeAdapter

from lp_agent import AgentAccessError, AgentValidationError, LPAgent, RunLimits
from lp_agent.tests.helpers import ScriptedModel, answer_item, environment_for
from lp_agent.types import (
    AccessContext,
    ModelFinished,
    ModelItem,
    ModelMessage,
    ModelOutputItem,
    ModelTextDelta,
    OutputText,
    ReasoningItem,
    ScopeSelection,
    ToolCall,
)


def test_direct_result_without_observer_and_independent_submissions():
    async def scenario():
        model = ScriptedModel(
            [
                ModelTextDelta(delta="Hello"),
                ModelTextDelta(delta=" there"),
                answer_item("Hello there"),
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
        assert model.requests[0].input[-1].content == "  First question  "
        assert len(model.requests[1].input) == 1
        assert model.requests[1].input[-1].content == "Second question"
        assert "court" in model.requests[0].instructions
        assert all(request.tools == () for request in model.requests)
        assert model.closed

    asyncio.run(scenario())


def test_checkpoint_retains_model_items_and_instruction_artifact_without_public_reasoning():
    async def scenario():
        reasoning = ReasoningItem(
            id="rs_1", summary=(), encrypted_content="private continuation"
        )
        answer = ModelMessage(
            role="assistant",
            id="msg_1",
            phase="final_answer",
            status="completed",
            content=(
                OutputText(
                    text="Hello",
                    annotations=({"type": "citation", "source": "court"},),
                ),
            ),
        )
        model = ScriptedModel(
            [
                ModelOutputItem(item=reasoning),
                ModelTextDelta(delta="Hello"),
                ModelOutputItem(item=answer),
                ModelFinished(reason="stop"),
            ]
        )
        environment = environment_for(model)
        async with LPAgent(environment=environment) as agent:
            run = await agent.run(message="  Question  ")
            assert (await run.result()).text == "Hello"
            events = [event.model_dump_json() async for event in run.events()]
        checkpoint = await environment.runs.checkpoint(
            access=environment.access, run_id=run.run_id
        )
        data = checkpoint.data
        assert data["model_request"] == model.requests[0].model_dump(
            mode="json"
        )
        assert TypeAdapter(tuple[ModelItem, ...]).validate_python(
            data["model_output"]
        ) == (reasoning, answer)
        assert data["model_finished"] == {"type": "finished", "reason": "stop"}
        artifact = data["instruction_artifact"]
        canonical = artifact["canonical_json"].encode("utf-8")
        assert hashlib.sha256(canonical).hexdigest() == artifact["sha256"]
        assert json.loads(canonical) == {
            "format": "lp_agent.instructions.v1",
            "instructions": model.requests[0].instructions,
            "tools": [],
        }
        assert "private continuation" not in "".join(events)
        data["model_output"].clear()
        saved = await environment.runs.checkpoint(
            access=environment.access, run_id=run.run_id
        )
        assert len(saved.data["model_output"]) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "item,code",
    [
        (
            ModelMessage(
                role="assistant", content="Partial", status="incomplete"
            ),
            "incomplete_response",
        ),
        (ReasoningItem(id="rs_1", summary=()), "incomplete_response"),
        (
            ToolCall(call_id="call_1", name="lookup", arguments="{}"),
            "tools_unavailable",
        ),
    ],
)
def test_output_items_do_not_turn_incomplete_responses_or_tool_calls_into_success(
    item, code
):
    async def scenario():
        environment = environment_for(
            ScriptedModel(
                [
                    ModelTextDelta(delta="Partial"),
                    ModelOutputItem(item=item),
                    ModelFinished(reason="stop"),
                ]
            )
        )
        async with LPAgent(environment=environment) as agent:
            run = await agent.run(message="Question")
            assert (await run.result()).error.code == code
        checkpoint = await environment.runs.checkpoint(
            access=environment.access, run_id=run.run_id
        )
        assert checkpoint.data["model_output"] == [
            item.model_dump(mode="json")
        ]
        assert checkpoint.data["model_finished"]["reason"] == "stop"

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
                [
                    ModelTextDelta(delta="Done"),
                    answer_item("Done"),
                    ModelFinished(reason="stop"),
                ]
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
