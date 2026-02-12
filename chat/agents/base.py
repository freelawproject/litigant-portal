import json
import logging
from collections.abc import Iterator
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal, TypedDict
from uuid import UUID

import litellm
from django.http import HttpRequest
from pydantic import BaseModel
from pydantic import Field as PydanticField

if TYPE_CHECKING:
    from chat.models import ChatSession

litellm.drop_params = True

logger = logging.getLogger(__name__)

Field = PydanticField


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


Message = Annotated[
    SystemMessage | UserMessage | AssistantMessage | ToolMessage,
    Field(discriminator="role"),
]


# =============================================================================
# Stream Event Types
# =============================================================================


class ContentDeltaEvent(TypedDict):
    """A chunk of content streamed from the assistant."""

    type: Literal["content_delta"]
    content: str


class ToolCallEvent(TypedDict):
    """Event indicating the assistant is calling a tool."""

    type: Literal["tool_call"]
    id: str
    name: str
    args: dict[str, Any]


class ToolResponseEvent(TypedDict, total=False):
    """Event containing the result of a tool execution.

    The `data` field contains structured data for the frontend.
    The `response` field is omitted from streaming by default.
    """

    type: Literal["tool_response"]
    id: str
    name: str
    data: dict[str, Any]


class DoneEvent(TypedDict):
    """Event indicating the stream is complete."""

    type: Literal["done"]


class ErrorEvent(TypedDict):
    """Event indicating an error occurred."""

    type: Literal["error"]
    error: str


StreamEvent = (
    ContentDeltaEvent
    | ToolCallEvent
    | ToolResponseEvent
    | DoneEvent
    | ErrorEvent
)


# =============================================================================
# Agent Classes
# =============================================================================


class ToolOutput(BaseModel):
    """Output from a tool execution.

    Tools can return either a string (shorthand for just response) or a
    ToolOutput with both response (for the LLM) and data (for the frontend).

    Example:
        def __call__(self, agent: Agent) -> ToolOutput:
            return ToolOutput(
                response=f"Weather in {self.location}: 72F, sunny",
                data={"location": self.location, "temp_f": 72, "condition": "sunny"}
            )
    """

    response: str
    data: dict[str, Any] | None = None


class Tool(BaseModel):
    """Base class for agent tools.

    Extend this class and define fields as tool parameters.

    Example:
        class WeatherTool(Tool):
            '''Get the current weather for a location.'''
            location: str = Field(description="City name")

            def __call__(self, agent: Agent) -> ToolOutput:
                return ToolOutput(
                    response=f"Weather in {self.location}: 72F, sunny",
                    data={"location": self.location, "temp_f": 72}
                )

    You can also return a plain string for simple cases:

        def __call__(self, agent: Agent) -> str:
            return f"Weather in {self.location}: 72F, sunny"
    """

    def __call__(self, agent: "Agent") -> ToolOutput | str | None:
        """Execute the tool.

        Override this method to implement tool logic.
        Return a ToolOutput for structured data, or a string for simple responses.
        You can also store data in agent.state.
        """
        pass

    @classmethod
    def get_schema(cls) -> dict:
        """Export the tool schema for LLM function calling."""
        return {
            "type": "function",
            "function": {
                "name": cls.__name__,
                "description": cls.__doc__,
                "parameters": cls.model_json_schema(),
            },
        }

    class Config:
        """Configuration to allow extra methods on the BaseModel."""

        extra = "allow"


class Agent:
    """A litellm wrapper for tool-calling agents with streaming support.

    Subclass this to create domain-specific agents with default configurations.
    All messages are plain dicts at runtime for easy serialization.

    Example:
        class LegalAssistant(Agent):
            default_model = "groq/llama-3.3-70b-versatile"
            default_tools = [SearchDocuments, GetCourtInfo]
            default_messages = [
                {"role": "system", "content": "You are a helpful legal assistant..."}
            ]
    """

    default_model: ClassVar[str] = "groq/llama-3.3-70b-versatile"
    default_tools: ClassVar[list[type[Tool]]] = []
    default_max_steps: ClassVar[int] = 30
    default_messages: ClassVar[list[Message]] = []
    default_completion_args: ClassVar[dict[str, Any]] = {}

    def __init__(
        self,
        model: str | None = None,
        tools: list[type[Tool]] | None = None,
        messages: list[Message] | None = None,
        state: dict | None = None,
        max_steps: int | None = None,
        session: type["ChatSession"] | None = None,
        **completion_args: Any,
    ):
        """Initialize the agent.

        Args:
            model: LiteLLM model string (e.g., "groq/llama-3.3-70b-versatile").
            tools: List of Tool classes available to the agent.
            messages: Initial message history (dicts matching Message schema).
            state: Initial state dictionary for tool data storage.
            max_steps: Maximum number of agent steps (tool call loops).
            session: ChatSession object to associate with the agent.
            **completion_args: Additional args passed to litellm.completion().
        """
        self.session = session
        self.model = model or self.default_model
        self.completion_args = {
            **self.default_completion_args,
            **completion_args,
        }

        # Set up tools
        tool_classes = tools if tools is not None else self.default_tools
        self.tools = {tool.__name__: tool for tool in tool_classes}
        self.tool_schemas = [
            tool.get_schema() for tool in tool_classes
        ] or None

        # Set up messages
        if messages is not None:
            self.messages: list[Message] = list(messages)
        else:
            self.messages = list(self.default_messages)

        self.state = state or {}
        self.max_steps = max_steps or self.default_max_steps
        self.last_response = None

    @property
    def messages_for_llm(self) -> list[dict[str, Any]]:
        """Return messages sanitized for LLM API calls.

        Strips out fields like `data` that aren't valid for the API.
        """
        messages: list[dict[str, Any]] = []
        for msg in self.messages:
            if msg.get("role") == "tool" and "data" in msg:
                messages.append({k: v for k, v in msg.items() if k != "data"})
            else:
                messages.append(dict(msg))
        return messages

    def add_message(self, message: Message):
        """Add a message to the agent's message history."""
        from chat.models import Message as MessageModel

        self.messages.append(message)
        if self.session:
            MessageModel.objects.create(session=self.session, data=message)

    def execute_tool(
        self, tool_call: ToolCall
    ) -> tuple[ToolMessage, ToolResponseEvent]:
        """Execute a single tool call.

        Returns:
            A tuple of (tool_message, tool_response_event):
            - tool_message: The full message to store (includes data)
            - tool_response_event: The event to stream to frontend (data only)
        """
        function = tool_call.get("function", {})
        tool_name = function.get("name", "")
        tool_id = tool_call.get("id", "") or ""
        tool_class = self.tools.get(tool_name)

        try:
            if not tool_class:
                raise ValueError(f"Unknown tool: {tool_name}")

            tool_args = json.loads(function.get("arguments", "{}"))
            tool_instance = tool_class(**tool_args)
            result = tool_instance(self)

            # Normalize result to ToolOutput
            if result is None:
                output = ToolOutput(response="Success")
            elif isinstance(result, str):
                output = ToolOutput(response=result)
            elif isinstance(result, ToolOutput):
                output = result
            else:
                output = ToolOutput(**result)

        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            output = ToolOutput(response=f"Error: {e}")

        # Build the tool message
        tool_msg: ToolMessage = {
            "role": "tool",
            "tool_call_id": tool_id,
            "name": tool_name,
            "content": output.response,
        }
        if output.data is not None:
            tool_msg["data"] = output.data

        # Build the event
        response_event: ToolResponseEvent = {
            "type": "tool_response",
            "id": tool_id,
            "name": tool_name,
        }
        if output.data is not None:
            response_event["data"] = output.data

        return tool_msg, response_event

    def stream_run(
        self,
        messages: list[Message] | str | None = None,
        **completion_args: Any,
    ) -> Iterator[StreamEvent]:
        """Run agent loop with streaming, yielding events as they occur.

        Args:
            messages: Initial user message(s) to add to history.
            **completion_args: Override completion arguments.

        Yields:
            Event dicts for frontend consumption.
        """
        # Add initial messages
        if messages is not None:
            if isinstance(messages, str):
                user_msg: UserMessage = {"role": "user", "content": messages}
                self.add_message(user_msg)
            else:
                for msg in messages:
                    self.add_message(msg)

        try:
            for _ in range(self.max_steps):
                # Prepare completion args
                call_args = {
                    "model": self.model,
                    "messages": self.messages_for_llm,
                    "tools": self.tool_schemas,
                    "stream": True,
                    **self.completion_args,
                    **completion_args,
                }

                # Stream the response
                full_content: list[str] = []
                tool_calls: list[ToolCall] = []

                for chunk in litellm.completion(**call_args):
                    choice = chunk.choices[0]
                    delta = choice.delta

                    # Yield content deltas
                    if delta.content:
                        full_content.append(delta.content)
                        content_event: ContentDeltaEvent = {
                            "type": "content_delta",
                            "content": delta.content,
                        }
                        yield content_event

                    # Accumulate tool calls from stream
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            # Extend tool_calls list if needed
                            while tc.index >= len(tool_calls):
                                tool_calls.append(
                                    {
                                        "id": None,
                                        "type": "function",
                                        "function": {
                                            "name": "",
                                            "arguments": "",
                                        },
                                    }
                                )
                            # Update the tool call at this index
                            if tc.id:
                                tool_calls[tc.index]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls[tc.index]["function"][
                                        "name"
                                    ] = tc.function.name
                                if tc.function.arguments:
                                    tool_calls[tc.index]["function"][
                                        "arguments"
                                    ] += tc.function.arguments

                # Store assistant message
                assistant_msg: AssistantMessage = {
                    "role": "assistant",
                    "content": "".join(full_content),
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                self.add_message(assistant_msg)

                # If we have tool calls, yield them and execute
                if tool_calls:
                    for tool_call in tool_calls:
                        function = tool_call.get("function", {})
                        # Yield tool call event
                        try:
                            args_dict = json.loads(
                                function.get("arguments", "{}")
                            )
                        except json.JSONDecodeError:
                            args_dict = {}

                        tool_call_event: ToolCallEvent = {
                            "type": "tool_call",
                            "id": tool_call.get("id") or "",
                            "name": function.get("name", ""),
                            "args": args_dict,
                        }
                        yield tool_call_event

                        # Execute tool
                        tool_msg, tool_response_event = self.execute_tool(
                            tool_call
                        )

                        # Store message (with data) and yield event (data only)
                        self.add_message(tool_msg)
                        yield tool_response_event
                else:
                    break

            done_event: DoneEvent = {"type": "done"}
            yield done_event

        except Exception as e:
            logger.error(f"Agent error: {e}")
            error_event: ErrorEvent = {"type": "error", "error": str(e)}
            yield error_event

    def ping(self) -> bool:
        """Check if the agent's model/provider is accessible."""
        try:
            litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            return True
        except Exception as e:
            logger.warning(f"Health check failed for {self.model}: {e}")
            return False

    @classmethod
    def from_session_id(
        cls,
        request: HttpRequest,
        session_id: str | UUID | None = None,
        **kwargs: Any,
    ) -> "Agent":
        """Create an agent from a session ID.

        If no session ID is provided, a new session is created.
        """
        from chat.models import ChatSession
        from chat.models import Message as MessageModel

        if not request.session.session_key:
            request.session.create()
        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key if not user else ""

        if not session_id:
            session = ChatSession.objects.create(
                user=user, session_key=session_key
            )
            agent = cls(session=session, **kwargs)
            for msg in agent.messages:
                MessageModel.objects.create(session=session, data=msg)
            return agent
        else:
            try:
                session = ChatSession.objects.get(id=session_id)
            except ChatSession.DoesNotExist:
                raise ValueError(f"Session {session_id} not found")
            # Verify ownership: check user for auth sessions, session_key for anonymous
            if session.user:
                if session.user != user:
                    raise PermissionError("Unauthorized access to session")
            else:
                if session.session_key != session_key:
                    raise PermissionError("Unauthorized access to session")
            messages = [
                m.data for m in session.messages.order_by("created_at")
            ]
            agent = cls(session=session, messages=messages, **kwargs)
            return agent

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Hook for custom workflow logic."""
        pass
