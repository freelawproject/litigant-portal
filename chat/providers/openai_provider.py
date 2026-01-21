import json
import logging
from collections.abc import Iterator
from typing import Any

import openai
from django.conf import settings

from .base import BaseLLMProvider, ChatMessage

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI provider for GPT models."""

    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(self):
        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY setting is required for OpenAI provider. "
                "Get a key at https://platform.openai.com"
            )
        self.client = openai.OpenAI(api_key=api_key)
        self.model = self._get_model()
        self.max_tokens = settings.CHAT_MAX_TOKENS

    def _get_model(self) -> str:
        """Get the model to use."""
        model = settings.CHAT_MODEL
        # Use OpenAI default if configured model is for different provider
        if model.startswith("llama") or ":" in model:
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
        """Stream response tokens from OpenAI."""
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
                temperature=0.3,
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except openai.AuthenticationError as e:
            logger.error(f"OpenAI authentication error (check API key): {e}")
            raise
        except openai.RateLimitError as e:
            logger.error(f"OpenAI rate limit exceeded: {e}")
            raise
        except openai.APIStatusError as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def generate_response(
        self,
        messages: list[ChatMessage],
        context: str | None = None,
    ) -> str:
        """Generate a complete response from OpenAI."""
        system = self._build_system_prompt(context)
        formatted_messages = [{"role": "system", "content": system}] + [
            {"role": m.role, "content": m.content} for m in messages
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=formatted_messages,
                temperature=0.3,
            )
            return response.choices[0].message.content
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def generate_json_response(
        self,
        messages: list[ChatMessage],
        system_prompt: str,
    ) -> dict[str, Any]:
        """Generate a JSON response from OpenAI using JSON mode."""
        formatted_messages = [{"role": "system", "content": system_prompt}] + [
            {"role": m.role, "content": m.content} for m in messages
        ]

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=formatted_messages,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    def health_check(self) -> bool:
        """Check if OpenAI API is responding."""
        try:
            self.client.chat.completions.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception as e:
            logger.warning(f"OpenAI health check failed: {e}")
            return False
