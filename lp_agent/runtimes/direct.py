"""
Direct admission, task ownership, event delivery, and shutdown.
"""

import asyncio
from collections.abc import AsyncGenerator

from lp_agent.errors import AgentValidationError
from lp_agent.flows.engagement import Engagement, EngagementFlow
from lp_agent.runtimes.stream import EventStream
from lp_agent.types import (
    ChoiceAnswer,
    EventPayload,
    RunEvent,
    RunOutcome,
    RunRequest,
    RunStatus,
)


class DirectRuntime:
    """
    Serialize admission with shutdown, then own every accepted task.
    """

    def __init__(self, flow: EngagementFlow) -> None:
        self._flow = flow
        self._admission = asyncio.Lock()
        self._runs: list[DirectRun] = []
        self._closed = False
        self._stream_claimed = False

    async def submit(self, request: RunRequest) -> "DirectRun":
        if self._stream_claimed:
            raise AgentValidationError(
                "The synchronous stream owns this agent."
            )
        return await self._accept(request)

    async def _accept(self, request: RunRequest) -> "DirectRun":
        async with self._admission:
            if self._closed:
                raise AgentValidationError("This agent is closed.")
            if self._flow.configuration.interrupt_behavior != "reject":
                raise NotImplementedError(
                    "Queue and steer are not implemented yet."
                )
            engagement = await self._flow.prepare(request)
            run = DirectRun(engagement)
            self._runs.append(run)
            return run

    def stream(self, request: RunRequest) -> EventStream:
        if self._stream_claimed or self._admission.locked() or self._runs:
            raise AgentValidationError(
                "Synchronous streaming requires an unused agent."
            )
        stream = EventStream(
            submit=lambda: self._accept(request), close_agent=self.aclose
        )
        self._stream_claimed = True
        return stream

    async def aclose(self) -> None:
        async with self._admission:
            # Preparation already holding this lock finishes acceptance first.
            self._closed = True
            for run in self._runs:
                run.request_cancel()
            results = await asyncio.gather(
                *(run.result() for run in self._runs), return_exceptions=True
            )
            self._runs.clear()
            for result in results:
                if isinstance(result, BaseException):
                    raise result


class DirectRun:
    """
    Schedule a prepared flow and expose one live event consumer.
    """

    def __init__(self, engagement: Engagement) -> None:
        self._engagement = engagement
        self._events: asyncio.Queue[RunEvent | None] = asyncio.Queue()
        self._observed = False
        self._executing = False
        self._cancel_requested = False
        self._task = asyncio.create_task(self._execute())

    @property
    def run_id(self) -> str:
        return self._engagement.initial_status.run_id

    @property
    def conversation_id(self) -> str:
        return self._engagement.initial_status.conversation_id

    async def status(self) -> RunStatus:
        return await self._engagement.status()

    async def events(self) -> AsyncGenerator[RunEvent]:
        if self._observed:
            raise AgentValidationError(
                "This run already has an event observer."
            )
        self._observed = True
        while (event := await self._events.get()) is not None:
            yield event
        # Surface unexpected storage failures as well as normal outcomes.
        await self.result()

    async def result(self) -> RunOutcome:
        return await asyncio.shield(self._task)

    async def respond(self, question_id: str, answer: ChoiceAnswer) -> None:
        await self._engagement.respond(question_id, answer)

    def request_cancel(self) -> None:
        if not self._task.done() and not self._cancel_requested:
            self._cancel_requested = True
            if self._executing:
                self._task.cancel()

    async def cancel(self) -> None:
        self.request_cancel()
        await self.result()

    def _emit(self, payload: EventPayload) -> None:
        self._events.put_nowait(
            RunEvent(**self._engagement.reference, payload=payload)
        )

    async def _execute(self) -> RunOutcome:
        try:
            self._executing = True
            try:
                outcome = await self._engagement.execute(
                    self._emit, cancelled=self._cancel_requested
                )
            finally:
                self._executing = False
            # Cancellation joins an in-progress terminal commit intact.
            await self._engagement.finish(outcome, self._emit)
            return outcome
        finally:
            self._events.put_nowait(None)
