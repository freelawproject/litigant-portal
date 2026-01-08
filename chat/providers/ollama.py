import logging
from collections.abc import Iterator

import openai
from django.conf import settings

from .base import BaseLLMProvider, ChatMessage

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Ollama provider for local LLM inference."""

    DEFAULT_BASE_URL = "http://host.docker.internal:11434/v1"
    DEFAULT_MODEL = "llama3.2:3b"

    def __init__(self):
        base_url = getattr(settings, "OLLAMA_BASE_URL", self.DEFAULT_BASE_URL)
        self.client = openai.OpenAI(
            api_key="ollama",  # Ollama doesn't need a real key
            base_url=base_url,
        )
        self.model = self._get_model()
        self.max_tokens = settings.CHAT_MAX_TOKENS

    def _get_model(self) -> str:
        """Get the model to use."""
        model = settings.CHAT_MODEL
        # Use default if it's a cloud provider model
        if model.startswith(("gpt-", "claude-", "gemini-")) or "/" in model:
            return self.DEFAULT_MODEL
        return model

    def _build_system_prompt(self, context: str | None = None) -> str:
        """Build the system prompt, optionally with RAG context."""
        system = settings.CHAT_SYSTEM_PROMPT
        if context:
            system += (
                f"\n\nRelevant context from our knowledge base:\n{context}"
            )
        return system

    def stream_response(
        self,
        messages: list[ChatMessage],
        context: str | None = None,
    ) -> Iterator[str]:
        """Stream response tokens from Ollama."""
        system = self._build_system_prompt(context)
        formatted_messages = [{"role": "system", "content": system}] + [
            {"role": m.role, "content": m.content} for m in messages
        ]

        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=formatted_messages,
                stream=True,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except openai.APIConnectionError as e:
            logger.error(f"Ollama connection error (is Ollama running?): {e}")
            raise
        except openai.APIStatusError as e:
            logger.error(f"Ollama API error: {e}")
            raise

    def generate_response(
        self,
        messages: list[ChatMessage],
        context: str | None = None,
    ) -> str:
        """Generate a complete response from Ollama."""
        system = self._build_system_prompt(context)
        formatted_messages = [{"role": "system", "content": system}] + [
            {"role": m.role, "content": m.content} for m in messages
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=formatted_messages,
            )
            return response.choices[0].message.content
        except openai.APIError as e:
            logger.error(f"Ollama API error: {e}")
            raise

    def health_check(self) -> bool:
        """Check if Ollama is responding."""
        try:
            self.client.chat.completions.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False
