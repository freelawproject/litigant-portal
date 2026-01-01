from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass


@dataclass
class ChatMessage:
    """A message in a chat conversation."""

    role: str  # "user", "assistant", or "system"
    content: str


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def stream_response(
        self,
        messages: list[ChatMessage],
        context: str | None = None,
    ) -> Iterator[str]:
        """
        Generate a streaming response from the LLM.

        Args:
            messages: List of chat messages in the conversation.
            context: Optional RAG context to include in the system prompt.

        Yields:
            Response tokens as they are generated.
        """
        pass

    @abstractmethod
    def generate_response(
        self,
        messages: list[ChatMessage],
        context: str | None = None,
    ) -> str:
        """
        Generate a complete response from the LLM.

        Args:
            messages: List of chat messages in the conversation.
            context: Optional RAG context to include in the system prompt.

        Returns:
            The complete response text.
        """
        pass

    def health_check(self) -> bool:
        """
        Check if the provider is available and responding.

        Returns:
            True if the provider is healthy, False otherwise.
        """
        return True
