"""
Normalize LiteLLM's Bedrock stream without exposing provider objects to core.
"""

import asyncio
import logging
import re
from collections.abc import AsyncGenerator, Mapping
from time import monotonic
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, SecretStr, TypeAdapter, ValidationError

from lp_agent.errors import AgentValidationError, ModelProviderError
from lp_agent.types import (
    ModelEvent,
    ModelFinished,
    ModelMessage,
    ModelOutputItem,
    ModelRequest,
    ModelTextDelta,
    OutputText,
    ReasoningItem,
    ReasoningSummary,
    ReasoningText,
    Refusal,
    ToolCall,
)

logger = logging.getLogger(__name__)

MODEL_CHOICES = (
    ("bedrock_mantle/openai.gpt-5.6-luna", "GPT-5.6 Luna"),
    ("bedrock_mantle/openai.gpt-5.6-terra", "GPT-5.6 Terra"),
    ("bedrock_mantle/openai.gpt-5.6-sol", "GPT-5.6 Sol"),
    ("bedrock_mantle/zai.glm-4.7-flash", "GLM 4.7 Flash"),
)

_OUTPUT_MODELS = {
    model.model_fields["type"].default: model
    for model in (
        ModelMessage,
        ToolCall,
        ReasoningItem,
        OutputText,
        Refusal,
        ReasoningSummary,
        ReasoningText,
    )
}


def _known_fields(
    value: dict, model: type[BaseModel] | None = None
) -> tuple[dict, int]:
    """
    Drop extra typed fields without traversing open metadata dictionaries.
    """
    if model is None:
        model = _OUTPUT_MODELS.get(value.get("type"))
    if model is None:
        return value, 0
    data = {
        key: item for key, item in value.items() if key in model.model_fields
    }
    ignored = len(value) - len(data)
    for key in ("content", "summary"):
        if not isinstance(data.get(key), list | tuple):
            continue
        part_model = None
        if model is ReasoningItem:
            part_model = (
                ReasoningSummary if key == "summary" else ReasoningText
            )
        parts = []
        for part in data[key]:
            if isinstance(part, dict):
                part, count = _known_fields(part, part_model)
                ignored += count
            parts.append(part)
        data[key] = parts
    return data, ignored


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
    done: dict[int, BaseModel | dict], output: list, *, translated: bool
) -> tuple[list[ModelOutputItem], Exception | None, int]:
    """
    Retain valid output in terminal order before reporting assembly failures.
    """
    previous = {}
    for value in done.values():
        try:
            item = _data(value)
        except (TypeError, ValueError):
            # Validate malformed buffered items only if terminal output uses them.
            continue
        if isinstance(item.get("id"), str):
            previous[item["id"]] = item
    items = []
    seen = set()
    error = None
    ignored = 0
    for value in output or [done[index] for index in sorted(done)]:
        try:
            item = _data(value)
            item_id = item.get("id")
            if isinstance(item_id, str):
                if item_id in seen:
                    raise ValueError("Duplicate model output item.")
                seen.add(item_id)
                item = previous.get(item_id, {}) | item
            item = _item_data(item, translated=translated)
            item, count = _known_fields(item)
            ignored += count
            if item.get("type") == "reasoning":
                item.setdefault("summary", [])
            items.append(ModelOutputItem.model_validate({"item": item}))
        except (TypeError, ValueError) as exc:
            if error is None:
                error = exc
    return items, error, ignored


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
            reason="length"
            if reason == "max_output_tokens"
            else "content_filter"
            if reason == "content_filter"
            else "other"
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


@runtime_checkable
class _AsyncCloseable(Protocol):
    async def aclose(self) -> None: ...


@runtime_checkable
class _NativeResponseStream(Protocol):
    stream_iterator: _AsyncCloseable
    response: _AsyncCloseable


async def _close_stream(stream: object) -> None:
    """
    Close the resource owned by native or translated LiteLLM Responses streams.

    LiteLLM 1.99's Responses iterators lack aclose(). The translated iterator
    owns a CustomStreamWrapper; the native iterator owns an HTTP response.
    """
    underlying = getattr(stream, "litellm_custom_stream_wrapper", None)
    if underlying is not None:
        await underlying.aclose()
    elif isinstance(stream, _NativeResponseStream):
        try:
            await stream.stream_iterator.aclose()
        finally:
            await stream.response.aclose()
    elif isinstance(stream, _AsyncCloseable):
        await stream.aclose()
    else:
        raise TypeError("Unrecognized provider stream resource.")


def _provider_error(
    error: Exception,
    *,
    model: str,
    stage: Literal["request", "stream", "normalize", "cleanup"],
    started: float,
    stream: object,
) -> ModelProviderError:
    """
    Extract allowlisted metadata without reading exception messages or bodies.
    """
    import httpx
    from litellm import APIConnectionError, Timeout

    original = getattr(error, "original_exception", None)
    errors = [error]
    if isinstance(original, Exception):
        errors.append(original)
    status = next(
        (
            value
            for item in errors
            if type(value := getattr(item, "status_code", None)) is int
            and 400 <= value <= 599
        ),
        None,
    )
    kind: Literal["failed", "unavailable", "timeout"] = "failed"
    if status in {408, 504} or any(
        isinstance(item, TimeoutError | httpx.TimeoutException | Timeout)
        for item in errors
    ):
        kind = "timeout"
    elif (
        status == 429
        or (status is not None and status >= 500)
        or any(
            isinstance(item, httpx.NetworkError | APIConnectionError)
            for item in errors
        )
    ):
        kind = "unavailable"

    request_id = None
    for source in [stream, *errors]:
        response = getattr(source, "response", None)
        candidates = [getattr(source, "request_id", None)]
        for headers in (
            getattr(response, "headers", None),
            getattr(source, "headers", None),
        ):
            if isinstance(headers, Mapping):
                candidates.extend(
                    headers.get(name)
                    for name in (
                        "x-request-id",
                        "x-amzn-requestid",
                        "x-amzn-request-id",
                        "x-amz-request-id",
                    )
                )
        request_id = next(
            (
                value
                for value in candidates
                if isinstance(value, str)
                and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", value)
            ),
            None,
        )
        if request_id is not None:
            break
    return ModelProviderError(
        kind=kind,
        model=model,
        stage=stage,
        exception_class=type(error).__name__,
        status_code=status,
        elapsed_seconds=monotonic() - started,
        request_id=request_id,
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

    @property
    def supports_tools(self) -> bool:
        """
        Native Responses models preserve preparation tool calls and history.
        """
        return self.model != "bedrock_mantle/zai.glm-4.7-flash"

    async def stream(
        self, request: ModelRequest
    ) -> AsyncGenerator[ModelEvent]:
        translated = self.model == "bedrock_mantle/zai.glm-4.7-flash"
        if translated:
            if request.tools or any(
                not isinstance(item, ModelMessage | ReasoningItem)
                for item in request.input
            ):
                raise AgentValidationError(
                    "Select a native Bedrock model for guided conversations."
                )
            for item in request.input:
                if (
                    not isinstance(item, ModelMessage)
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

        options: dict[str, object] = (
            {} if translated else {"include": ["reasoning.encrypted_content"]}
        )
        if request.tools:
            options["tools"] = [
                tool.model_dump(mode="json") for tool in request.tools
            ]
        started = monotonic()
        stage: Literal["request", "stream", "normalize", "cleanup"] = "request"
        response = None
        failed = False
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
            stage = "stream"
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
                        done[event["output_index"]] = event["item"]
                    elif kind in {
                        "response.completed",
                        "response.incomplete",
                        "response.failed",
                    }:
                        result = event["response"]
                        break
                    elif kind == "error":
                        raise RuntimeError("The model response failed.")
            except (Exception, asyncio.CancelledError) as exc:
                error = exc
            # Preserve completed items before propagating failure or
            # cancellation. GeneratorExit must bypass these yields.
            items, assembly_error, ignored = _assembled_items(
                done,
                result.get("output", []) if result is not None else [],
                translated=translated,
            )
            if ignored:
                logger.warning(
                    "Ignored unfamiliar Bedrock metadata (model=%s, fields=%s)",
                    self.model,
                    ignored,
                )
            for output_item in items:
                yield output_item
            if error is not None:
                raise error
            stage = "normalize"
            if assembly_error is not None:
                raise assembly_error
            if result is not None:
                yield _finish(result, response, items)
        except Exception as exc:
            failed = True
            raise _provider_error(
                exc,
                model=self.model,
                stage=stage,
                started=started,
                stream=response,
            ) from None
        except BaseException:
            failed = True
            raise
        finally:
            try:
                try:
                    if response is not None:
                        await _close_stream(response)
                finally:
                    await client.close()
            except Exception as exc:
                cleanup_error = _provider_error(
                    exc,
                    model=self.model,
                    stage="cleanup",
                    started=started,
                    stream=response,
                )
                if not failed:
                    raise cleanup_error from None
                # Cleanup must not replace a provider failure or cancellation.
                logger.warning(
                    "Model cleanup failed (model=%s, exception_class=%s)",
                    self.model,
                    cleanup_error.exception_class,
                )
