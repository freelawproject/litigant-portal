from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict
from pydantic import Field as PydanticField

Field = PydanticField


class AgentState(BaseModel):
    """Base for an agent's per-thread state model."""

    model_config = ConfigDict(extra="allow")


class ToolOutput(BaseModel):
    """Result of running a tool."""

    # Returned to the model as the tool message content.
    result: str
    # Arbitrary structured data streamed to the frontend for rendering.
    render_data: dict[str, Any] | None = None
    # When True, the agent regenerates its system prompt before the next
    # step (instead of only when a new user message is submitted).
    refresh_system_prompt: bool = False


class Tool(BaseModel):
    """Base class for agent tools."""

    model_config = ConfigDict(extra="allow")

    tool_call_template: ClassVar[str | bool | None] = None
    tool_result_template: ClassVar[str | bool | None] = None

    def __call__(self, *, thread_id) -> ToolOutput:
        """Run the tool against ``thread_id`` and return its output."""
        raise NotImplementedError

    @classmethod
    def get_schema(cls) -> dict:
        """Export the tool schema for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": cls.__name__,
                "description": cls.__doc__ or "",
                "parameters": cls.model_json_schema(),
            },
        }


class Agent:
    """A configuration object for a tool-calling agent."""

    completion_args: ClassVar[dict[str, Any]] = {}
    state_schema: ClassVar[type[AgentState]] = AgentState
    tools: ClassVar[list[type[Tool]]] = []

    def generate_system_prompt(self, *, thread_id) -> str:
        """Build the system prompt for ``thread_id`` from its state."""
        raise NotImplementedError

    @property
    def tools_by_name(self) -> dict[str, type[Tool]]:
        """Map tool name -> tool class for dispatching tool calls."""
        return {tool.__name__: tool for tool in self.tools}

    @property
    def tool_schemas(self) -> list[dict] | None:
        """Tool schemas for the LLM, or None when the agent has no tools."""
        return [tool.get_schema() for tool in self.tools] or None
