"""
Instance-local storage adapters for development runs and core tests.
"""

from uuid import uuid4

from lp_agent.errors import AgentAccessError, AgentValidationError
from lp_agent.types import (
    AccessContext,
    AgentConfiguration,
    Conversation,
    RunCheckpoint,
    RunOutcome,
    RunRequest,
    RunStatus,
    Scope,
    ScopeSelection,
)


class MemoryConversationStore:
    """
    Keep authorized conversations for the lifetime of this store.
    """

    def __init__(self) -> None:
        self._conversations: dict[str, Conversation] = {}

    async def create(
        self, *, access: AccessContext, scope: ScopeSelection
    ) -> Conversation:
        conversation = Conversation(
            conversation_id=str(uuid4()),
            identity_id=access.identity_id,
            scope=scope,
        )
        self._conversations[conversation.conversation_id] = conversation
        return conversation

    async def get(
        self, *, access: AccessContext, conversation_id: str
    ) -> Conversation:
        conversation = self._conversations.get(conversation_id)
        if (
            conversation is None
            or conversation.identity_id != access.identity_id
        ):
            raise AgentAccessError("Conversation is unavailable.")
        return conversation

    async def bind_scope(
        self, *, access: AccessContext, conversation_id: str, scope: Scope
    ) -> None:
        conversation = await self.get(
            access=access, conversation_id=conversation_id
        )
        for field in ("court", "topic"):
            selected = getattr(conversation.scope, field)
            if selected is not None and selected != getattr(scope, field):
                raise AgentAccessError("Conversation scope cannot change.")
        self._conversations[conversation_id] = conversation.model_copy(
            update={"scope": ScopeSelection(**scope.model_dump())}
        )


class MemoryRunStore:
    """
    Store run snapshots without a process-wide registry or durable recovery.
    """

    def __init__(self, conversations: MemoryConversationStore) -> None:
        self._conversations = conversations
        self._statuses: dict[str, RunStatus] = {}
        self._checkpoints: dict[str, RunCheckpoint] = {}
        self._outcomes: dict[str, RunOutcome] = {}

    async def create(
        self,
        *,
        access: AccessContext,
        conversation_id: str,
        request: RunRequest,
        configuration: AgentConfiguration,
    ) -> RunStatus:
        await self._conversations.get(
            access=access, conversation_id=conversation_id
        )
        status = RunStatus(
            run_id=str(uuid4()),
            conversation_id=conversation_id,
            state="queued",
        )
        self._statuses[status.run_id] = status
        return status

    async def status(self, *, access: AccessContext, run_id: str) -> RunStatus:
        status = self._statuses.get(run_id)
        if status is None:
            raise AgentAccessError("Run is unavailable.")
        await self._conversations.get(
            access=access, conversation_id=status.conversation_id
        )
        return status

    async def outcome(
        self, *, access: AccessContext, run_id: str
    ) -> RunOutcome | None:
        await self.status(access=access, run_id=run_id)
        return self._outcomes.get(run_id)

    async def checkpoint(
        self, *, access: AccessContext, run_id: str
    ) -> RunCheckpoint | None:
        await self.status(access=access, run_id=run_id)
        checkpoint = self._checkpoints.get(run_id)
        return checkpoint.model_copy(deep=True) if checkpoint else None

    async def commit_checkpoint(
        self,
        *,
        access: AccessContext,
        checkpoint: RunCheckpoint,
        status: RunStatus,
        outcome: RunOutcome | None = None,
    ) -> None:
        current = await self.status(access=access, run_id=status.run_id)
        for reference in (checkpoint, status, outcome):
            if reference is not None and (
                reference.run_id != current.run_id
                or reference.conversation_id != current.conversation_id
            ):
                raise AgentValidationError("Run references must match.")
        if outcome is not None and outcome.state != status.state:
            raise AgentValidationError("Outcome and status must match.")
        self._checkpoints[status.run_id] = checkpoint.model_copy(deep=True)
        self._statuses[status.run_id] = status
        if outcome is not None:
            self._outcomes[status.run_id] = outcome
