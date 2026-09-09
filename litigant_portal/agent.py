"""
Host entry point translating verified identity into package-owned options.
"""

from __future__ import annotations

from pydantic import SecretStr

from litigant_portal.app.models import UserIdentity
from lp_agent import AgentValidationError, LPAgent, RunLimits
from lp_agent.adapters.catalog import Court
from lp_agent.adapters.environment import Option, create_environment
from lp_agent.types import InterruptBehavior, Runtime


class PortalAgent(LPAgent):
    """
    Translate the Django identity and forward explicitly supplied options.
    """

    def __init__(
        self,
        *,
        identity: UserIdentity,
        model: Option[str],
        api_key: Option[str | SecretStr],
        catalog: Option[tuple[Court, ...]],
        court: Option[str | None] = None,
        topic: Option[str | None] = None,
        runtime: Runtime = "Workers",
        interrupt_behavior: InterruptBehavior = "reject",
        limits: RunLimits | None = None,
    ) -> None:
        if (
            not isinstance(identity, UserIdentity)
            or identity.pk is None
            or identity._state.adding
        ):
            raise AgentValidationError("a host-verified identity is required")
        super().__init__(
            environment=create_environment(
                identity_id=str(identity.pk),
                court=court,
                topic=topic,
                model=model,
                api_key=api_key,
                catalog=catalog,
            ),
            runtime=runtime,
            interrupt_behavior=interrupt_behavior,
            limits=limits,
        )
