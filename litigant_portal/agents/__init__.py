from importlib import import_module
from typing import TYPE_CHECKING, Any

from .base import Agent, AgentState, Field, Tool, ToolOutput

if TYPE_CHECKING:
    from .assistant import LitigantAssistant, LitigantAssistantState

__all__ = [
    "Agent",
    "AgentState",
    "Field",
    "Tool",
    "ToolOutput",
    "LitigantAssistant",
    "LitigantAssistantState",
]


def __getattr__(name: str) -> Any:
    """
    Keep Bedrock catalog imports independent of Django-dependent agents.
    """
    if name in {"LitigantAssistant", "LitigantAssistantState"}:
        return getattr(import_module(".assistant", __name__), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
