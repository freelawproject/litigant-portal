"""
The public agent facade and immutable execution configuration.
"""

from pydantic import TypeAdapter, ValidationError

from lp_agent.environment import AgentEnvironment
from lp_agent.errors import AgentValidationError
from lp_agent.flows.engagement import EngagementFlow
from lp_agent.interfaces import RunHandle
from lp_agent.runtimes.direct import DirectRuntime
from lp_agent.runtimes.stream import EventStream
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
    Configure a flow and runtime behind the shared agent interface.
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
            raise AgentValidationError.from_validation_error(exc) from exc
        if not isinstance(environment, AgentEnvironment):
            raise AgentValidationError(
                "environment must be an AgentEnvironment"
            )
        self._environment = environment
        self._execution = (
            DirectRuntime(EngagementFlow(environment, self._configuration))
            if runtime == "Direct"
            else None
        )

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

    def _executor(self) -> DirectRuntime:
        if self._execution is None:
            raise NotImplementedError(
                "Workers execution is not implemented yet."
            )
        return self._execution

    @staticmethod
    def _request(
        message: str,
        conversation_id: str | None,
        attachment_ids: tuple[str, ...],
    ) -> RunRequest:
        try:
            return RunRequest(
                message=message,
                conversation_id=conversation_id,
                attachment_ids=attachment_ids,
            )
        except ValidationError as exc:
            raise AgentValidationError.from_validation_error(exc) from exc

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
        request = self._request(message, conversation_id, attachment_ids)
        return await self._executor().submit(request)

    def stream(
        self,
        *,
        message: str,
        conversation_id: str | None = None,
        attachment_ids: tuple[str, ...] = (),
    ) -> EventStream:
        """
        Transfer this instance to a synchronous NDJSON event iterator.
        """
        request = self._request(message, conversation_id, attachment_ids)
        return self._executor().stream(request)

    async def aclose(self) -> None:
        """
        Wait for admission, then cancel and join owned Direct tasks.
        """
        if self._execution is not None:
            await self._execution.aclose()

    async def __aenter__(self) -> "LPAgent":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

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
