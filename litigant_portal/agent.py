"""
Host entry point translating verified identity into package-owned options.
"""

from __future__ import annotations

from django.conf import settings
from pydantic import SecretStr

from litigant_portal.app.models import UserIdentity
from lp_agent import AgentValidationError, LPAgent, RunLimits
from lp_agent.adapters.environment import Option, create_environment
from lp_agent.types import InterruptBehavior, Runtime


class PortalAgent(LPAgent):
    """
    Translate verified Django identity and supply host configuration.
    """

    def __init__(
        self,
        *,
        identity: UserIdentity,
        model: Option[str],
        judge: Option[str | None] = None,
        court: str | None = None,
        topic: str | None = None,
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
                judge=judge,
                api_key=SecretStr(settings.BEDROCK_API_KEY),
                resource_root=settings.BASE_DIR,
            ),
            runtime=runtime,
            interrupt_behavior=interrupt_behavior,
            limits=limits,
        )
