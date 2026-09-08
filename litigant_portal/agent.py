"""
Host entry point for the new agent; Django adapter wiring follows in PR2.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError

from lp_agent import AgentValidationError, LPAgent, RunLimits
from lp_agent.types import (
    AgentConfiguration,
    InterruptBehavior,
    Runtime,
    ScopeSelection,
)

if TYPE_CHECKING:
    from litigant_portal.app.models import UserIdentity


class PortalAgent(LPAgent):
    """
    Wire host-verified identity, application adapters, and portal defaults.
    """

    def __init__(
        self,
        *,
        identity: UserIdentity,
        court: str | None = None,
        topic: str | None = None,
        runtime: Runtime = "Workers",
        interrupt_behavior: InterruptBehavior = "reject",
        limits: RunLimits | None = None,
    ) -> None:
        try:
            AgentConfiguration(
                runtime=runtime,
                interrupt_behavior=interrupt_behavior,
                limits=RunLimits() if limits is None else limits,
            )
            ScopeSelection(court=court, topic=topic)
        except ValidationError as exc:
            raise AgentValidationError.from_validation_error(exc) from exc
        if identity is None:
            raise AgentValidationError("a host-verified identity is required")
        raise NotImplementedError(
            "Django environment construction is not implemented; "
            "PortalAgent adapter wiring follows in PR2."
        )
