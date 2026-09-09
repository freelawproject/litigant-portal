"""
The public agent facade. Runtime implementation starts in PR2.
"""

from pydantic import TypeAdapter, ValidationError

from lp_agent.environment import AgentEnvironment
from lp_agent.errors import AgentValidationError
from lp_agent.interfaces import RunHandle
from lp_agent.types import (
    AgentConfiguration,
    Identifier,
    InterruptBehavior,
    RunLimits,
    RunRequest,
    Runtime,
)


class LPAgent:
    """
    A reusable, async agent runner configured with host-supplied services.
    """

    def __init__(
        self,
        *,
        environment: AgentEnvironment,
        runtime: Runtime = "Direct",
        interrupt_behavior: InterruptBehavior = "reject",
        limits: RunLimits | None = None,
    ) -> None:
        try:
            self._configuration = AgentConfiguration(
                runtime=runtime,
                interrupt_behavior=interrupt_behavior,
                limits=RunLimits() if limits is None else limits,
            )
        except ValidationError as exc:
            raise AgentValidationError.from_validation_error(
                exc, models=(AgentConfiguration,)
            ) from exc
        if not isinstance(environment, AgentEnvironment):
            raise AgentValidationError(
                "environment must be an AgentEnvironment"
            )
        self._environment = environment

    @property
    def environment(self) -> AgentEnvironment:
        return self._environment

    @property
    def runtime(self) -> Runtime:
        return self._configuration.runtime

    @property
    def interrupt_behavior(self) -> InterruptBehavior:
        return self._configuration.interrupt_behavior

    @property
    def limits(self) -> RunLimits:
        return self._configuration.limits

    async def run(
        self,
        *,
        message: str,
        conversation_id: str | None = None,
        attachment_ids: tuple[str, ...] = (),
    ) -> RunHandle:
        """
        Submit a turn, creating a conversation when no ID is supplied.
        """
        try:
            RunRequest(
                message=message,
                conversation_id=conversation_id,
                attachment_ids=attachment_ids,
            )
        except ValidationError as exc:
            raise AgentValidationError.from_validation_error(
                exc, models=(RunRequest,)
            ) from exc
        raise NotImplementedError(
            f"{self.runtime} execution is not implemented yet."
        )

    async def get_run(self, run_id: str) -> RunHandle:
        """
        Recover an authorized handle after instance reconstruction.
        """
        try:
            TypeAdapter(Identifier).validate_python(run_id)
        except ValidationError as exc:
            raise AgentValidationError.from_validation_error(exc) from exc
        raise NotImplementedError("Run recovery is not implemented yet.")

    async def serve_mcp(self) -> None:
        """
        TODO: expose this agent through a Model Context Protocol adapter.
        """
        raise NotImplementedError("MCP exposure is not implemented yet.")
