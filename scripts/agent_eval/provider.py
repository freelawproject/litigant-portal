"""
Observe LiteLLM calls without changing requests, streams, or agent behavior.
"""

import inspect
import os
import time
from contextlib import ExitStack
from contextvars import ContextVar
from unittest.mock import patch

from .schema import Config

_OBSERVING = ContextVar("agent_eval_observing", default=False)
REQUEST_FIELDS = {
    "model",
    "messages",
    "input",
    "instructions",
    "tools",
    "stream",
    "temperature",
    "top_p",
    "max_tokens",
    "max_output_tokens",
    "reasoning",
    "stream_options",
    "num_retries",
    "caching",
    "store",
    "include",
}


def data(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    return value


def safe(value):
    """
    Save request evidence without credentials or encrypted reasoning blobs.
    """
    value = data(value)
    if isinstance(value, dict):
        return {
            key: safe(item)
            for key, item in value.items()
            if key not in {"api_key", "authorization", "encrypted_content"}
        }
    if isinstance(value, list | tuple):
        return [safe(item) for item in value]
    if isinstance(value, str):
        token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")
        return value.replace(token, "[redacted]") if token else value
    return value


def usage_cost(response, model: str, config: Config) -> dict:
    """
    Keep unknown usage/pricing distinct from measured zero expenditure.
    """
    import litellm

    raw = data(response) or {}
    usage = raw.get("usage") or {}
    incoming = usage.get("input_tokens", usage.get("prompt_tokens"))
    outgoing = usage.get("output_tokens", usage.get("completion_tokens"))
    details = (
        usage.get("input_tokens_details")
        or usage.get("prompt_tokens_details")
        or {}
    )
    cached = details.get(
        "cached_tokens", usage.get("cache_read_input_tokens", 0)
    )
    result = {
        "usage": usage or None,
        "input_tokens": incoming,
        "output_tokens": outgoing,
        "cached_input_tokens": cached if usage else None,
        "cost_usd": None,
        "pricing": None,
    }
    if incoming is None or outgoing is None:
        return result
    override = config.prices.get(model)
    if override:
        result["pricing"] = {
            "basis": "config override",
            **override.model_dump(),
        }
        if usage.get("cache_creation_input_tokens") or (
            cached and override.cached_input_per_million is None
        ):
            return result
        result["cost_usd"] = (
            (incoming - cached) * override.input_per_million
            + outgoing * override.output_per_million
            + cached * (override.cached_input_per_million or 0)
        ) / 1_000_000
        return result
    try:
        info = litellm.get_model_info(model=model)
        if any(
            info.get(key) is None
            for key in ("input_cost_per_token", "output_cost_per_token")
        ):
            return result
        result["pricing"] = {
            "basis": "LiteLLM model pricing snapshot",
            "rates": {
                key: value
                for key, value in info.items()
                if "cost" in key and value is not None
            },
        }
        cost = litellm.completion_cost(
            completion_response=response, model=model
        )
        if cost is not None and cost >= 0:
            result["cost_usd"] = cost
    except Exception:
        # Missing price data must never turn an otherwise good answer into
        # an execution failure, or masquerade as a free model call.
        pass
    return result


class Stream:
    """
    Forward stream attributes and closing behavior as well as every chunk.
    """

    def __init__(self, source, observe):
        self.source = source
        self.observe = observe
        self.iterator = None
        self.async_iterator = None

    def __getattr__(self, name):
        return getattr(self.source, name)

    def __iter__(self):
        if self.iterator is None:
            self.iterator = iter(self.source)
        return self

    def __next__(self):
        if self.iterator is None:
            self.iterator = iter(self.source)
        value = next(self.iterator)
        self.observe(value)
        return value

    def __aiter__(self):
        if self.async_iterator is None:
            self.async_iterator = self.source.__aiter__()
        return self

    async def __anext__(self):
        if self.async_iterator is None:
            self.async_iterator = self.source.__aiter__()
        value = await self.async_iterator.__anext__()
        self.observe(value)
        return value


class Observer:
    """
    A process-local observer for the system or evaluator, never both at once.
    """

    def __init__(self, calls: list, config: Config, flush=lambda: None):
        self.calls = calls
        self.config = config
        self.flush = flush
        self.stack = ExitStack()

    def start(self, api, kwargs):
        call = {
            "api": api,
            "model": kwargs.get("model"),
            "request": safe(
                {k: v for k, v in kwargs.items() if k in REQUEST_FIELDS}
            ),
            "usage": None,
            "cost_usd": None,
            "finish_reason": None,
        }
        self.calls.append(call)
        self.flush()
        started = time.monotonic()

        def observe(value):
            raw = data(value)
            response = raw.get("response", raw)
            if response.get("usage"):
                call.update(usage_cost(response, call["model"], self.config))
            if raw.get("type") in {
                "response.completed",
                "response.incomplete",
                "response.failed",
            }:
                call["finish_reason"] = response.get("status")
            for choice in raw.get("choices", []):
                if choice.get("finish_reason"):
                    call["finish_reason"] = choice["finish_reason"]
            call["elapsed_seconds"] = time.monotonic() - started
            if response.get("usage") or call["finish_reason"]:
                self.flush()

        return call, observe

    def __enter__(self):
        import litellm

        completion, responses = litellm.completion, litellm.aresponses

        def sync(*args, **kwargs):
            if _OBSERVING.get():
                return completion(*args, **kwargs)
            token = _OBSERVING.set(True)
            call, observe = self.start("completion", kwargs)
            try:
                result = completion(*args, **kwargs)
                if kwargs.get("stream"):
                    return Stream(result, observe)
                observe(result)
                return result
            except Exception as exc:
                call["error"] = type(exc).__name__
                call["error_message"] = safe(str(exc))[:2000]
                self.flush()
                raise
            finally:
                _OBSERVING.reset(token)

        async def async_response(*args, **kwargs):
            if _OBSERVING.get():
                return await responses(*args, **kwargs)
            token = _OBSERVING.set(True)
            call, observe = self.start("responses", kwargs)
            try:
                result = await responses(*args, **kwargs)
                if kwargs.get("stream"):
                    return Stream(result, observe)
                observe(result)
                return result
            except Exception as exc:
                call["error"] = type(exc).__name__
                call["error_message"] = safe(str(exc))[:2000]
                self.flush()
                raise
            finally:
                _OBSERVING.reset(token)

        self.stack.enter_context(patch.object(litellm, "completion", sync))
        self.stack.enter_context(
            patch.object(litellm, "aresponses", async_response)
        )
        return self

    def __exit__(self, *exc):
        self.stack.close()
        self.flush()


async def close_stream(stream):
    close = getattr(stream, "aclose", None) or getattr(stream, "close", None)
    if close:
        result = close()
        if inspect.isawaitable(result):
            await result
