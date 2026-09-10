"""
Prepare an authorized engagement and produce one scoped model response.
"""

import asyncio
import logging
from collections.abc import Callable
from contextlib import aclosing
from dataclasses import dataclass, field

from lp_agent.errors import AgentAccessError, AgentValidationError
from lp_agent.flows.prompts import system_prompt
from lp_agent.identity import AgentIdentity, ResourceScope
from lp_agent.types import (
    AgentConfiguration,
    CancelledOutcome,
    ChoiceAnswer,
    CompletedOutcome,
    EventPayload,
    FailedOutcome,
    ModelFinished,
    ModelItem,
    ModelMessage,
    ModelOutputItem,
    ModelRequest,
    ModelTextDelta,
    OutcomeEvent,
    OutputText,
    PublicError,
    Refusal,
    RunCheckpoint,
    RunLimits,
    RunOutcome,
    RunRequest,
    RunState,
    RunStatus,
    Scope,
    StatusEvent,
    TextEvent,
    ToolCall,
)
from lp_agent.utils.audit import InstructionArtifact

logger = logging.getLogger(__name__)


class EngagementFlow:
    """
    Resolve scope once and prepare independent turns against injected services.
    """

    def __init__(
        self, environment: AgentIdentity, configuration: AgentConfiguration
    ) -> None:
        self.environment = environment
        self.configuration = configuration
        self._scoped: ResourceScope | None = None

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
        model_request = ModelRequest(
            instructions=system_prompt(scoped.scope),
            input=(ModelMessage(role="user", content=request.message),),
        )
        return Engagement(
            environment=self.environment,
            scoped=scoped,
            initial_status=status,
            request=request,
            limits=self.configuration.limits,
            model_request=model_request,
            instruction_artifact=InstructionArtifact.from_request(
                model_request
            ),
        )

    async def _bind_scope(self) -> ResourceScope:
        if self._scoped is not None:
            return self._scoped
        selection = self.environment.scope
        if selection.court is None or selection.topic is None:
            raise AgentValidationError(
                "Select a court and topic before sending."
            )
        scope = Scope(court=selection.court, topic=selection.topic)
        access = self.environment.access
        scoped = await self.environment.scope_factory.bind(
            access=access, scope=scope
        )
        if scoped.access != access or scoped.scope != scope:
            raise AgentAccessError(
                "Bound services do not match the requested scope."
            )
        self._scoped = scoped
        return scoped


@dataclass(kw_only=True)
class Engagement:
    """
    Own a prepared turn's model steps, state transitions, and safe outcomes.
    """

    environment: AgentIdentity
    scoped: ResourceScope
    initial_status: RunStatus
    request: RunRequest
    limits: RunLimits
    model_request: ModelRequest = field(repr=False)
    instruction_artifact: InstructionArtifact = field(repr=False)
    output_items: list[ModelItem] = field(
        default_factory=list, init=False, repr=False
    )
    model_finished: ModelFinished | None = field(default=None, init=False)

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
                data={
                    "request": self.request.model_dump(mode="json"),
                    "model_request": self.model_request.model_dump(
                        mode="json"
                    ),
                    "model_output": [
                        item.model_dump(mode="json")
                        for item in self.output_items
                    ],
                    "model_finished": (
                        self.model_finished.model_dump(mode="json")
                        if self.model_finished is not None
                        else None
                    ),
                    "instruction_artifact": {
                        "canonical_json": self.instruction_artifact.canonical_bytes().decode(
                            "utf-8"
                        ),
                        "sha256": self.instruction_artifact.content_hash(),
                    },
                },
            ),
            status=status,
            outcome=outcome,
        )
        emit(StatusEvent(status=status))

    async def _model_response(
        self, emit: Callable[[EventPayload], None]
    ) -> RunOutcome:
        async with aclosing(
            self.scoped.model.stream(self.model_request)
        ) as stream:
            async for event in stream:
                if isinstance(event, ModelTextDelta):
                    emit(TextEvent(delta=event.delta))
                elif isinstance(event, ModelOutputItem):
                    self.output_items.append(event.item.model_copy(deep=True))
                elif isinstance(event, ModelFinished):
                    self.model_finished = event
        if any(isinstance(item, ToolCall) for item in self.output_items):
            return self._failure(
                "tools_unavailable", "This run has no tools available."
            )
        messages = [
            item
            for item in self.output_items
            if isinstance(item, ModelMessage)
        ]
        if (
            self.model_finished is None
            or self.model_finished.reason != "stop"
            or not messages
            or any(
                item.status in {"incomplete", "in_progress"}
                for item in self.output_items
            )
        ):
            return self._failure(
                "incomplete_response", "The model did not finish its response."
            )
        parts = []
        for message in messages:
            if isinstance(message.content, str):
                parts.append(message.content)
            else:
                for part in message.content:
                    if isinstance(part, OutputText):
                        parts.append(part.text)
                    elif isinstance(part, Refusal):
                        parts.append(part.refusal)
        return CompletedOutcome(**self.reference, text="".join(parts))
