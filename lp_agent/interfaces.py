"""
Async boundaries implemented by package runtimes and service adapters.
"""

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Protocol

from lp_agent.types import (
    AccessContext,
    AgentConfiguration,
    ChoiceAnswer,
    Conversation,
    ModelEvent,
    ModelRequest,
    RunCheckpoint,
    RunEvent,
    RunOutcome,
    RunRequest,
    RunStatus,
    Scope,
    ScopeSelection,
)

if TYPE_CHECKING:
    from lp_agent.environment import ScopedEnvironment


class RunHandle(Protocol):
    """
    An authorized reference to work, independent of a request's lifetime.
    """

    @property
    def run_id(self) -> str: ...

    @property
    def conversation_id(self) -> str: ...

    async def status(self) -> RunStatus: ...

    def events(self) -> AsyncGenerator[RunEvent]:
        """
        Observe live events; no public cursor replay is provided initially.
        """
        ...

    async def result(self) -> RunOutcome:
        """
        Wait for a terminal outcome, including across pauses for user input.
        """
        ...

    async def respond(self, question_id: str, answer: ChoiceAnswer) -> None:
        """
        Validate a reply to the pending question and resume the same run.
        """
        ...

    async def cancel(self) -> None:
        """
        Request cancellation; status and result report acknowledgement.
        """
        ...


class ConversationStore(Protocol):
    """
    Authorize every operation; enforce ownership and fixed resolved scope.
    """

    async def create(
        self, *, access: AccessContext, scope: ScopeSelection
    ) -> Conversation: ...

    async def get(
        self, *, access: AccessContext, conversation_id: str
    ) -> Conversation: ...

    async def bind_scope(
        self, *, access: AccessContext, conversation_id: str, scope: Scope
    ) -> None: ...


class RunStore(Protocol):
    """
    Authorized persistence boundary; PR2 supplies transactions and locking.
    """

    async def create(
        self,
        *,
        access: AccessContext,
        conversation_id: str,
        request: RunRequest,
        configuration: AgentConfiguration,
    ) -> RunStatus: ...

    async def status(
        self, *, access: AccessContext, run_id: str
    ) -> RunStatus: ...

    async def outcome(
        self, *, access: AccessContext, run_id: str
    ) -> RunOutcome | None: ...

    async def checkpoint(
        self, *, access: AccessContext, run_id: str
    ) -> RunCheckpoint | None: ...

    async def commit_checkpoint(
        self,
        *,
        access: AccessContext,
        checkpoint: RunCheckpoint,
        status: RunStatus,
        outcome: RunOutcome | None = None,
    ) -> None:
        """
        Atomically save completed work, consumed inputs, status, and outcome.

        All references must identify the same authorized run. PR2 defines
        checkpoint contents and the transaction/concurrency implementation.
        """
        ...


class ModelClient(Protocol):
    """
    Stream text deltas and assembled Responses output items in provider order.

    Streams support aclose() and emit ModelFinished on a finished response.
    Preserve reasoning, message metadata, and argument strings for history.
    PR2 validates arguments before dispatch; adapters reject unsupported schema
    features or strict mode instead of changing them silently. These events
    are internal agent signals, not the Responses HTTP streaming protocol.
    """

    def stream(self, request: ModelRequest) -> AsyncGenerator[ModelEvent]: ...


class ScopeFactory(Protocol):
    """
    Build services bound to the same verified identity and complete scope.
    """

    async def bind(
        self, *, access: AccessContext, scope: Scope
    ) -> "ScopedEnvironment": ...
