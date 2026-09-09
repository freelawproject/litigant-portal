"""
Normalize LiteLLM's Bedrock stream without exposing provider objects to core.
"""

from collections.abc import AsyncGenerator

from pydantic import BaseModel, SecretStr, TypeAdapter, ValidationError

from lp_agent.errors import AgentValidationError
from lp_agent.types import (
    ModelEvent,
    ModelFinished,
    ModelMessage,
    ModelOutputItem,
    ModelRequest,
    ModelTextDelta,
    OutputText,
    ReasoningItem,
    ToolCall,
)

MODEL_CHOICES = (
    ("bedrock_mantle/openai.gpt-5.6-luna", "GPT-5.6 Luna"),
    ("bedrock_mantle/openai.gpt-5.6-terra", "GPT-5.6 Terra"),
    ("bedrock_mantle/openai.gpt-5.6-sol", "GPT-5.6 Sol"),
    ("bedrock_mantle/zai.glm-4.7-flash", "GLM 4.7 Flash"),
)


def _data(value: BaseModel | dict) -> dict:
    """
    Read SDK values without retaining provider objects in the agent contract.
    """
    return (
        value.model_dump(mode="python", exclude_none=True)
        if isinstance(value, BaseModel)
        else dict(value)
    )


def _item_data(value: BaseModel | dict, *, translated: bool) -> dict:
    """
    Normalize LiteLLM's synthetic reasoning content to Responses item fields.
    """
    item = _data(value)
    if translated and item.get("type") == "reasoning":
        if item.pop("role", "assistant") != "assistant":
            raise ValueError("Invalid reasoning role.")
        content = []
        for part in item.get("content", ()):
            part = dict(part)
            if part.get("type") == "output_text":
                if part.pop("annotations", ()) or part.pop("logprobs", None):
                    raise ValueError("Unsupported reasoning metadata.")
                part["type"] = "reasoning_text"
            content.append(part)
        if "content" in item:
            item["content"] = content
    return item


def _assembled_items(
    done: dict[int, dict], output: list, *, translated: bool
) -> list[ModelOutputItem]:
    """
    Prefer terminal output order and metadata, without replaying done items.
    """
    previous = {item["id"]: item for item in done.values() if item.get("id")}
    items = []
    seen = set()
    for value in output or [done[index] for index in sorted(done)]:
        item = _item_data(value, translated=translated)
        item_id = item.get("id")
        if item_id:
            if item_id in seen:
                raise ValueError("Duplicate model output item.")
            seen.add(item_id)
            item = previous.get(item_id, {}) | item
        if item.get("type") == "reasoning":
            item.setdefault("summary", [])
        items.append(ModelOutputItem(item=item))
    return items


def _finish(
    response: dict, stream: object, items: list[ModelOutputItem]
) -> ModelFinished:
    """
    Check actual response status and provider termination, including emulation.
    """
    status = response.get("status")
    if status == "failed":
        raise RuntimeError("The model response failed.")
    # LiteLLM can synthesize a successful completion on EOF. This field records
    # the provider's finish signal rather than that synthesized fallback.
    underlying = getattr(stream, "litellm_custom_stream_wrapper", None)
    if underlying is not None:
        reason = underlying.received_finish_reason
        if reason not in {"stop", "tool_calls", "function_call"}:
            return ModelFinished(
                reason=reason
                if reason in {"length", "content_filter"}
                else "other"
            )
    if status == "incomplete":
        reason = (response.get("incomplete_details") or {}).get("reason")
        return ModelFinished(
            reason={
                "max_output_tokens": "length",
                "content_filter": "content_filter",
            }.get(reason, "other")
        )
    if status != "completed":
        return ModelFinished(reason="other")
    if underlying is not None and underlying.received_finish_reason in {
        "tool_calls",
        "function_call",
    }:
        return ModelFinished(reason="tool_calls")
    return ModelFinished(
        reason="tool_calls"
        if any(isinstance(event.item, ToolCall) for event in items)
        else "stop"
    )


async def _close_stream(stream: object) -> None:
    """
    Close the resource owned by native or translated LiteLLM Responses streams.

    LiteLLM 1.99's Responses iterators lack aclose(). The translated iterator
    owns a CustomStreamWrapper; the native iterator owns an HTTP response.
    """
    underlying = getattr(stream, "litellm_custom_stream_wrapper", None)
    if underlying is not None:
        await underlying.aclose()
    elif hasattr(stream, "response"):
        try:
            await stream.stream_iterator.aclose()
        finally:
            await stream.response.aclose()
    else:
        await stream.aclose()


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
            not isinstance(item, ModelMessage | ReasoningItem)
            for item in request.input
        ):
            raise NotImplementedError("Tool calls are not connected yet.")
        translated = self.model == "bedrock_mantle/zai.glm-4.7-flash"
        if translated:
            for item in request.input:
                if (
                    isinstance(item, ReasoningItem)
                    or item.id is not None
                    or item.status is not None
                    or item.phase is not None
                    or (
                        not isinstance(item.content, str)
                        and any(
                            isinstance(part, OutputText)
                            and (part.annotations or part.logprobs)
                            for part in item.content
                        )
                    )
                ):
                    raise AgentValidationError(
                        "This model cannot preserve the supplied continuation metadata."
                    )
        # Import the optional SDK only when this adapter executes a request.
        from litellm import aresponses
        from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler

        options = (
            {} if translated else {"include": ["reasoning.encrypted_content"]}
        )
        client = AsyncHTTPHandler()
        try:
            response = await aresponses(
                model=self.model,
                api_key=self._api_key.get_secret_value(),
                client=client,
                instructions=request.instructions,
                input=[item.model_dump(mode="json") for item in request.input],
                stream=True,
                store=False,
                num_retries=0,
                caching=False,
                **options,
            )
            try:
                done = {}
                result = None
                error = None
                try:
                    async for chunk in response:
                        event = _data(chunk)
                        kind = event["type"]
                        if kind in {
                            "response.output_text.delta",
                            "response.refusal.delta",
                        }:
                            yield ModelTextDelta(delta=event["delta"])
                        elif kind == "response.output_item.done":
                            done[event["output_index"]] = _item_data(
                                event["item"], translated=translated
                            )
                        elif kind in {
                            "response.completed",
                            "response.incomplete",
                            "response.failed",
                        }:
                            result = event["response"]
                            break
                        elif kind == "error":
                            raise RuntimeError("The model response failed.")
                except Exception as exc:
                    error = exc
                # Preserve completed items on EOF or failure, without treating
                # either as a successful response. Cancellation skips this path.
                items = _assembled_items(
                    done,
                    result.get("output", []) if result is not None else [],
                    translated=translated,
                )
                for item in items:
                    yield item
                if error is not None:
                    raise error
                if result is not None:
                    yield _finish(result, response, items)
            finally:
                await _close_stream(response)
        finally:
            await client.close()
