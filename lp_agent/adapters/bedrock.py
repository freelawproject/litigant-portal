"""
Normalize LiteLLM's Bedrock stream without exposing provider objects to core.
"""

from collections.abc import AsyncGenerator
from contextlib import aclosing

from pydantic import SecretStr, TypeAdapter, ValidationError

from lp_agent.errors import AgentValidationError
from lp_agent.types import (
    ModelEvent,
    ModelFinished,
    ModelRequest,
    ModelTextDelta,
)

MODEL_CHOICES = (
    ("bedrock_mantle/openai.gpt-5.6-luna", "GPT-5.6 Luna"),
    ("bedrock_mantle/openai.gpt-5.6-terra", "GPT-5.6 Terra"),
    ("bedrock_mantle/openai.gpt-5.6-sol", "GPT-5.6 Sol"),
    ("bedrock_mantle/anthropic.claude-haiku-4-5", "Claude Haiku 4.5"),
    ("bedrock_mantle/zai.glm-4.7-flash", "GLM 4.7 Flash"),
)


class BedrockClient:
    """
    Use an allowlisted model and explicitly supplied Bedrock credentials.
    """

    def __init__(self, model: str, *, api_key: str | SecretStr) -> None:
        if not isinstance(model, str) or model not in dict(MODEL_CHOICES):
            raise AgentValidationError("Select an available Bedrock model.")
        self.model = model
        try:
            self._api_key = TypeAdapter(SecretStr).validate_python(api_key)
        except ValidationError:
            raise AgentValidationError(
                "A Bedrock API key is required."
            ) from None
        if not self._api_key.get_secret_value().strip():
            raise AgentValidationError("A Bedrock API key is required.")

    async def stream(
        self, request: ModelRequest
    ) -> AsyncGenerator[ModelEvent]:
        if request.tools or any(
            message.tool_calls or message.role == "tool"
            for message in request.messages
        ):
            raise NotImplementedError("Tool calls are not connected yet.")
        # Import the optional SDK only when this adapter executes a request.
        from litellm import acompletion

        response = await acompletion(
            model=self.model,
            api_key=self._api_key.get_secret_value(),
            messages=[
                {"role": message.role, "content": message.text}
                for message in request.messages
            ],
            stream=True,
            num_retries=0,
            caching=False,
        )
        async with aclosing(response):
            async for chunk in response:
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                if choice.delta.tool_calls:
                    raise NotImplementedError(
                        "No tools are available to this run."
                    )
                if choice.delta.content:
                    yield ModelTextDelta(delta=choice.delta.content)
                if choice.finish_reason:
                    reason = choice.finish_reason
                    yield ModelFinished(
                        reason=reason
                        if reason
                        in {"stop", "length", "tool_calls", "content_filter"}
                        else "other"
                    )
