"""
Assemble development services from resolved values or initialization callbacks.
"""

import inspect
from collections.abc import Callable

from pydantic import SecretStr, TypeAdapter, ValidationError

from lp_agent.adapters.bedrock import BedrockClient
from lp_agent.adapters.catalog import Court, StaticScopeCatalog
from lp_agent.adapters.memory import MemoryConversationStore, MemoryRunStore
from lp_agent.environment import AgentEnvironment, ScopedEnvironment
from lp_agent.errors import AgentAccessError, AgentValidationError
from lp_agent.interfaces import ModelClient
from lp_agent.types import AccessContext, Scope, ScopeSelection, SearchHit

type Option[T] = T | Callable[[], T]


def _resolve[T](value: Option[T], name: str) -> T:
    """
    Invoke synchronous callbacks once, without exposing callback error data.
    """
    try:
        resolved = value() if callable(value) else value
    except Exception:
        raise AgentValidationError(f"Unable to resolve {name}.") from None
    if inspect.isawaitable(resolved):
        if inspect.iscoroutine(resolved):
            resolved.close()
        raise AgentValidationError(f"{name} must resolve synchronously.")
    return resolved


def create_environment(
    *,
    identity_id: Option[str],
    model: Option[str],
    api_key: Option[str | SecretStr],
    catalog: Option[tuple[Court, ...]],
    court: Option[str | None] = None,
    topic: Option[str | None] = None,
) -> AgentEnvironment:
    """
    Resolve supplied options once and build an instance-local Bedrock environment.

    Callbacks may perform initialization I/O. Authentication and selection of
    permitted catalogue data remain the caller's responsibility.
    """
    try:
        access = AccessContext(
            identity_id=_resolve(identity_id, "identity_id")
        )
        scope = ScopeSelection(
            court=_resolve(court, "court"), topic=_resolve(topic, "topic")
        )
        choices = TypeAdapter(tuple[Court, ...]).validate_python(
            _resolve(catalog, "catalog")
        )
    except ValidationError as exc:
        raise AgentValidationError.from_validation_error(
            exc, models=(AccessContext, ScopeSelection)
        ) from None
    scopes = StaticScopeCatalog(access, choices)
    model_client = BedrockClient(
        _resolve(model, "model"), api_key=_resolve(api_key, "api_key")
    )
    conversations = MemoryConversationStore()
    return AgentEnvironment(
        access=access,
        scope=scope,
        conversations=conversations,
        runs=MemoryRunStore(conversations),
        catalog=scopes,
        scope_factory=ModelScopeFactory(access, model_client),
    )


class UnavailableSearch:
    """
    Keep the search boundary explicit until retrieval is implemented.
    """

    async def search(
        self,
        *,
        query: str,
        conversation_id: str,
        attachment_ids: tuple[str, ...] = (),
    ) -> tuple[SearchHit, ...]:
        raise NotImplementedError("Search is not connected yet.")


class ModelScopeFactory:
    """
    Bind the configured model to one verified identity and resolved scope.
    """

    def __init__(self, access: AccessContext, model: ModelClient) -> None:
        self._access = access
        self._model = model

    async def bind(
        self, *, access: AccessContext, scope: Scope
    ) -> ScopedEnvironment:
        if access != self._access:
            raise AgentAccessError("Scope is unavailable to this identity.")
        return ScopedEnvironment(
            access=access,
            scope=scope,
            model=self._model,
            corpus=UnavailableSearch(),
            documents=UnavailableSearch(),
        )
