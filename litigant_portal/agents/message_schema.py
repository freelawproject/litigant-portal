import logging
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    NotRequired,
    TypedDict,
)

from pydantic import Field as PydanticField

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

Field = PydanticField


def llm_completion(**kwargs):
    """Wrapper around litellm.completion() that injects default args."""
    import litellm

    kwargs.setdefault("drop_params", True)
    return litellm.completion(**kwargs)


# =============================================================================
# Message Types
# =============================================================================


class FunctionCall(TypedDict, total=False):
    """Function call details within a tool call."""

    name: str
    arguments: str


class ToolCall(TypedDict, total=False):
    """A tool call made by the assistant."""

    id: str | None
    type: Literal["function"]
    function: FunctionCall


class SystemMessage(TypedDict):
    """A system message that sets the assistant's behavior."""

    role: Literal["system"]
    content: str


class UserMessage(TypedDict):
    """A message from the user."""

    role: Literal["user"]
    content: str
    attachments: NotRequired[list[str]]


class AssistantMessage(TypedDict, total=False):
    """A message from the assistant, optionally with tool calls."""

    role: Literal["assistant"]
    content: str
    tool_calls: list[ToolCall]


class ToolMessage(TypedDict, total=False):
    """A response from a tool execution.

    The `data` field stores structured data for the frontend. It is stripped
    out when sending messages to the LLM API (via messages_for_llm).
    """

    role: Literal["tool"]
    tool_call_id: str
    name: str
    content: str
    data: dict[str, Any]


class MetaMessage(TypedDict, total=False):
    """An accounting-only record."""

    role: Literal["meta"]
    kind: str


MessageSchema = Annotated[
    SystemMessage | UserMessage | AssistantMessage | ToolMessage | MetaMessage,
    Field(discriminator="role"),
]
