from .base import (
    Agent,
    AssistantMessage,
    ContentDeltaEvent,
    DoneEvent,
    ErrorEvent,
    Field,
    FunctionCall,
    Message,
    StreamEvent,
    SystemMessage,
    Tool,
    ToolCall,
    ToolCallEvent,
    ToolMessage,
    ToolOutput,
    ToolResponseEvent,
    UserMessage,
)
from .litigant_assistant import LitigantAssistantAgent
from .weather import WeatherAgent

# Register agent classes here
agent_classes = [
    LitigantAssistantAgent,
    WeatherAgent,
]
agent_registry = {cls.__name__: cls for cls in agent_classes}


__all__ = [
    # Message types
    "FunctionCall",
    "ToolCall",
    "SystemMessage",
    "UserMessage",
    "AssistantMessage",
    "ToolMessage",
    "Message",
    # Stream event types
    "ContentDeltaEvent",
    "ToolCallEvent",
    "ToolResponseEvent",
    "DoneEvent",
    "ErrorEvent",
    "StreamEvent",
    # Core classes
    "Agent",
    "Tool",
    "ToolOutput",
    "Field",
    # Registry
    "agent_registry",
]
