"""
Prepare an authorized engagement and produce one scoped model response.
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import aclosing
from dataclasses import dataclass

from lp_agent.environment import AgentEnvironment, ScopedEnvironment
from lp_agent.errors import AgentAccessError, AgentValidationError
from lp_agent.flows.prompts import system_prompt
from lp_agent.types import (
    AgentConfiguration,
    CancelledOutcome,
    ChoiceAnswer,
    CompletedOutcome,
    EventPayload,
    FailedOutcome,
    ModelFinished,
    ModelMessage,
    ModelRequest,
    ModelTextDelta,
    OutcomeEvent,
    PublicError,
    RunCheckpoint,
    RunLimits,
    RunOutcome,
    RunRequest,
    RunState,
    RunStatus,
    Scope,
    StatusEvent,
    TextEvent,
)

logger = logging.getLogger(__name__)


class EngagementFlow:
    """
    Resolve scope once and prepare independent turns against injected services.
    """

    def __init__(
        self, environment: AgentEnvironment, configuration: AgentConfiguration
    ) -> None:
        self.environment = environment
        self.configuration = configuration
        self._scoped: ScopedEnvironment | None = None

    async def prepare(self, request: RunRequest) -> "Engagement":
        if request.conversation_id is not None or request.attachment_ids:
            raise NotImplementedError(
                "Conversation continuation and attachments are not implemented yet."
            )
        scoped = await self._bind_scope()
        conversation = await self.environment.conversations.create(
            access=self.environment.access, scope=self.environment.scope
        )
        status = await self.environment.runs.create(
            access=self.environment.access,
            conversation_id=conversation.conversation_id,
            request=request,
            configuration=self.configuration,
        )
        return Engagement(
            environment=self.environment,
            scoped=scoped,
            initial_status=status,
            request=request,
            limits=self.configuration.limits,
        )

    async def _bind_scope(self) -> ScopedEnvironment:
        if self._scoped is not None:
            return self._scoped
        selection = self.environment.scope
        if selection.court is None or selection.topic is None:
            raise AgentValidationError(
                "Select a court and topic before sending."
            )
        scope = Scope(court=selection.court, topic=selection.topic)
        access = self.environment.access
        courts = await self.environment.catalog.courts(access=access)
        topics = await self.environment.catalog.topics(
            access=access, court=scope.court
        )
        if scope.court not in {choice.choice_id for choice in courts} or (
            scope.topic not in {choice.choice_id for choice in topics}
        ):
            raise AgentAccessError(
                "The selected court and topic are unavailable."
            )
        scoped = await self.environment.scope_factory.bind(
            access=access, scope=scope
        )
        if scoped.access != access or scoped.scope != scope:
            raise AgentAccessError(
                "Bound services do not match the requested scope."
            )
        self._scoped = scoped
        return scoped


@dataclass(frozen=True, kw_only=True)
class Engagement:
    """
    Own a prepared turn's model steps, state transitions, and safe outcomes.
    """

    environment: AgentEnvironment
    scoped: ScopedEnvironment
    initial_status: RunStatus
    request: RunRequest
    limits: RunLimits

    @property
    def reference(self) -> dict[str, str]:
        return {
            "run_id": self.initial_status.run_id,
            "conversation_id": self.initial_status.conversation_id,
        }

    async def status(self) -> RunStatus:
        return await self.environment.runs.status(
            access=self.environment.access, run_id=self.initial_status.run_id
        )

    async def respond(self, question_id: str, answer: ChoiceAnswer) -> None:
        raise AgentValidationError("This run has no pending question.")

    async def execute(
        self,
        emit: Callable[[EventPayload], None],
        *,
        cancelled: bool = False,
    ) -> RunOutcome:
        try:
            await self._save("running", emit)
            if cancelled:
                raise asyncio.CancelledError
            async with asyncio.timeout(self.limits.max_active_seconds):
                outcome = await self._model_response(emit)
        except asyncio.CancelledError:
            outcome = CancelledOutcome(**self.reference)
        except TimeoutError:
            outcome = self._failure(
                "active_time_limit", "The run reached its active time limit."
            )
        except Exception:
            # Provider exceptions can contain prompts, output, and credentials.
            logger.warning(
                "Agent operation failed (run_id=%s)",
                self.initial_status.run_id,
            )
            outcome = self._failure(
                "model_failed", "The model response failed. Please try again."
            )
        return outcome

    async def finish(
        self, outcome: RunOutcome, emit: Callable[[EventPayload], None]
    ) -> None:
        """
        Commit the terminal state before publishing its outcome.
        """
        await self._save(outcome.state, emit, outcome)
        emit(OutcomeEvent(outcome=outcome))

    def _failure(self, code: str, message: str) -> FailedOutcome:
        return FailedOutcome(
            **self.reference, error=PublicError(code=code, message=message)
        )

    async def _save(
        self,
        state: RunState,
        emit: Callable[[EventPayload], None],
        outcome: RunOutcome | None = None,
    ) -> None:
        status = RunStatus(**self.reference, state=state)
        await self.environment.runs.commit_checkpoint(
            access=self.environment.access,
            checkpoint=RunCheckpoint(
                **self.reference,
                data={"request": self.request.model_dump(mode="json")},
            ),
            status=status,
            outcome=outcome,
        )
        emit(StatusEvent(status=status))

    async def _model_response(
        self, emit: Callable[[EventPayload], None]
    ) -> RunOutcome:
        request = ModelRequest(
            messages=(
                ModelMessage(
                    role="system", text=system_prompt(self.scoped.scope)
                ),
                ModelMessage(role="user", text=self.request.message),
            ),
        )
        parts: list[str] = []
        finished: ModelFinished | None = None
        async with aclosing(self.scoped.model.stream(request)) as stream:
            async for event in stream:
                if isinstance(event, ModelTextDelta):
                    parts.append(event.delta)
                    emit(TextEvent(delta=event.delta))
                elif isinstance(event, ModelFinished):
                    finished = event
                else:
                    return self._failure(
                        "tools_unavailable", "This run has no tools available."
                    )
        if finished is None or finished.reason != "stop":
            return self._failure(
                "incomplete_response", "The model did not finish its response."
            )
        return CompletedOutcome(**self.reference, text="".join(parts))
