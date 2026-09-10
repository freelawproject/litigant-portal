"""
Live service dependencies, separate from serializable contracts.
"""

from dataclasses import dataclass, field
from pathlib import Path

from lp_agent.errors import AgentValidationError
from lp_agent.interfaces import (
    ConversationStore,
    ModelClient,
    RunStore,
    ScopeFactory,
)
from lp_agent.types import AccessContext, Scope, ScopeSelection


@dataclass(frozen=True, kw_only=True)
class ResourceScope:
    """
    Services bound once to a verified identity, court, and topic.
    """

    access: AccessContext
    scope: Scope
    model: ModelClient
    judge: ModelClient | None = None
    resource_root: Path | None = None

    def __post_init__(self) -> None:
        """
        Reject unresolved scope at the normal execution boundary.
        """
        if not isinstance(self.access, AccessContext):
            raise AgentValidationError("access must be an AccessContext")
        if not isinstance(self.scope, Scope):
            raise AgentValidationError("scoped services require a full Scope")
        if self.judge is None:
            object.__setattr__(self, "judge", self.model)


@dataclass(frozen=True, kw_only=True)
class AgentIdentity:
    """
    Host-verified context and services for scope discovery and execution.
    """

    access: AccessContext
    conversations: ConversationStore
    runs: RunStore
    scope_factory: ScopeFactory
    scope: ScopeSelection = field(default_factory=ScopeSelection)

    def __post_init__(self) -> None:
        """
        Require validated data without invoking any host service.
        """
        if not isinstance(self.access, AccessContext):
            raise AgentValidationError("access must be an AccessContext")
        if not isinstance(self.scope, ScopeSelection):
            raise AgentValidationError("scope must be a ScopeSelection")
