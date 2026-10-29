"""
Assemble development services from resolved values or initialization callbacks.
"""

import inspect
from collections.abc import Callable
from pathlib import Path

from pydantic import SecretStr, TypeAdapter, ValidationError

from lp_agent.adapters.bedrock import BedrockClient
from lp_agent.adapters.bedrock_models import (
    BedrockPolicy,
    ResolvedBedrockModel,
)
from lp_agent.adapters.memory import MemoryConversationStore, MemoryRunStore
from lp_agent.errors import AgentAccessError, AgentValidationError
from lp_agent.identity import AgentIdentity, ResourceScope
from lp_agent.interfaces import ModelClient
from lp_agent.types import AccessContext, Scope, ScopeSelection

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
    model: Option[str | ResolvedBedrockModel],
    api_key: Option[str | SecretStr],
    resource_root: Option[str | Path],
    judge: Option[str | ResolvedBedrockModel | None] = None,
    policy: BedrockPolicy | None = None,
    model_resolver: Callable[[str], ResolvedBedrockModel] | None = None,
    on_model_error: Callable[[Exception], None] | None = None,
    court: str | None = None,
    topic: str | None = None,
) -> AgentIdentity:
    """
    Resolve supplied options once and build an instance-local Bedrock environment.

    Callbacks may perform initialization I/O; court and topic are plain keys.
    Resource lookup waits until a flow requests corpus. An omitted judge uses
    the primary model client.
    """
    try:
        access = AccessContext(
            identity_id=_resolve(identity_id, "identity_id")
        )
        scope = ScopeSelection(court=court, topic=topic)
    except ValidationError as exc:
        raise AgentValidationError.from_validation_error(
            exc, models=(AccessContext, ScopeSelection)
        ) from None
    root = _resolve(resource_root, "resource_root")
    if (
        not isinstance(root, str | Path)
        or not str(root).strip()
        or "\0" in str(root)
    ):
        raise AgentValidationError("resource_root must be a nonempty path.")
    try:
        key = TypeAdapter(SecretStr).validate_python(
            _resolve(api_key, "api_key")
        )
    except ValidationError:
        raise AgentValidationError("A Bedrock API key is required.") from None
    if not key.get_secret_value().strip():
        raise AgentValidationError("A Bedrock API key is required.")
    selected = _resolve(model, "model")
    judge_model = _resolve(judge, "judge")
    if not isinstance(selected, str | ResolvedBedrockModel) or not isinstance(
        judge_model, str | ResolvedBedrockModel | None
    ):
        raise AgentValidationError("Select an available Bedrock model.")
    preferences = tuple(
        value for value in (selected, judge_model) if isinstance(value, str)
    )
    resolved = {}
    if preferences:
        if model_resolver is not None:
            resolved = {
                value: model_resolver(value)
                for value in dict.fromkeys(preferences)
            }
        else:
            if policy is None:
                raise AgentValidationError(
                    "A Bedrock deployment policy is required."
                )
            from lp_agent.adapters.bedrock_discovery import resolve_models

            resolved = resolve_models(
                policy=policy,
                api_key=key.get_secret_value(),
                preferences=preferences,
                required=frozenset({"text", "stream"}),
            )
    model_client = BedrockClient(
        resolved[selected] if isinstance(selected, str) else selected,
        api_key=key,
        on_error=on_model_error,
    )
    judge_client = (
        BedrockClient(
            resolved[judge_model]
            if isinstance(judge_model, str)
            else judge_model,
            api_key=key,
            on_error=on_model_error,
        )
        if judge_model is not None
        else None
    )
    conversations = MemoryConversationStore()
    return AgentIdentity(
        access=access,
        scope=scope,
        conversations=conversations,
        runs=MemoryRunStore(conversations),
        scope_factory=ModelScopeFactory(
            access, model_client, judge_client, Path(root).absolute()
        ),
    )


class ModelScopeFactory:
    """
    Bind the configured model to one verified identity and resolved scope.
    """

    def __init__(
        self,
        access: AccessContext,
        model: ModelClient,
        judge: ModelClient | None,
        resource_root: Path,
    ) -> None:
        self._access = access
        self._model = model
        self._judge = judge
        self._resource_root = resource_root

    async def bind(
        self, *, access: AccessContext, scope: Scope
    ) -> ResourceScope:
        if access != self._access:
            raise AgentAccessError("Scope is unavailable to this identity.")
        return ResourceScope(
            access=access,
            scope=scope,
            model=self._model,
            judge=self._judge,
            resource_root=self._resource_root,
        )
