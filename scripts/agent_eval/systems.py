"""
Thin adapters around the raw provider and unchanged application entry points.
"""

import asyncio
import json
import os
from pathlib import Path

from .provider import close_stream, data


async def raw(question: str, model: str, emit) -> dict:
    """
    Send exactly the user question, without an instruction or system message.
    """
    import litellm
    from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler

    client = AsyncHTTPHandler()
    try:
        stream = await litellm.aresponses(
            model=model,
            input=question,
            api_key=os.environ["AWS_BEARER_TOKEN_BEDROCK"],
            client=client,
            stream=True,
            store=False,
            num_retries=0,
            caching=False,
        )
        terminal = None
        try:
            async for chunk in stream:
                event = data(chunk)
                kind = event["type"]
                if kind in {
                    "response.output_text.delta",
                    "response.refusal.delta",
                }:
                    emit({"type": "text", "delta": event["delta"]})
                elif kind in {
                    "response.completed",
                    "response.incomplete",
                    "response.failed",
                }:
                    terminal = event["response"]
                    break
                elif kind == "error":
                    raise RuntimeError("Provider reported a stream error.")
        finally:
            await close_stream(stream)
        if terminal is None or terminal.get("status") != "completed":
            raise RuntimeError("Provider did not complete the response.")
        output = terminal.get("output", [])
        if not any(item.get("type") == "message" for item in output) or any(
            item.get("status") not in {None, "completed"} for item in output
        ):
            raise RuntimeError(
                "Provider did not complete an assistant message."
            )
        translated = getattr(stream, "litellm_custom_stream_wrapper", None)
        if (
            translated is not None
            and translated.received_finish_reason != "stop"
        ):
            raise RuntimeError(
                "Translated model stream did not finish normally."
            )
        if any(
            item.get("type") not in {"message", "reasoning"}
            for item in terminal.get("output", [])
        ):
            raise RuntimeError(
                "Raw model returned an unsupported output item."
            )
        return {"provider_status": "completed"}
    finally:
        await client.close()


def old(case, model: str, identity, emit) -> dict:
    from litigant_portal.agents.assistant import LitigantAssistant
    from litigant_portal.app.models import ChatThread
    from litigant_portal.app.selectors.chat_engine import (
        chat_thread_export_data,
    )
    from litigant_portal.app.services.chat_engine import chat_stream

    response = chat_stream(
        identity=identity,
        message=case.question,
        agent_class=LitigantAssistant,
        thread_type="user_chat",
        model=model,
    )
    thread_id, error, done = None, None, False
    try:
        for frame in response:
            text = frame.decode() if isinstance(frame, bytes) else frame
            event = json.loads(text.removeprefix("data: ").strip())
            kind = event["type"]
            if kind == "thread":
                thread_id = event["thread_id"]
            elif kind == "content_delta":
                emit({"type": "text", "delta": event["content"]})
                continue
            elif kind == "error":
                error = event["error"]
            elif kind == "done":
                done = True
            emit(event)
    finally:
        response.close()
    export = chat_thread_export_data(
        thread=ChatThread.objects.get(pk=thread_id)
    )
    messages = [m["data"] for m in export["messages"] if not m["meta"]]
    if (
        error
        or not done
        or not messages
        or messages[-1].get("role") != "assistant"
        or messages[-1].get("tool_calls")
    ):
        emit({"type": "thread_export", "data": export})
        raise RuntimeError(
            error or "Old agent stopped without a final answer."
        )
    return {
        "thread_id": thread_id,
        "thread_export": export,
        "corpus_load_observed": any(
            message.get("name") == "LoadTopicFlow"
            and message.get("content", "").startswith(
                "The active topic flow is now "
            )
            for message in messages
            if message.get("role") == "tool"
        ),
    }


async def new(
    case, model: str, identity, emit, resource_root: str | None
) -> dict:
    from django.test.utils import override_settings

    from litigant_portal.agent import PortalAgent

    options = {"BASE_DIR": Path(resource_root)} if resource_root else {}
    with override_settings(**options):
        agent = PortalAgent(
            identity=identity,
            model=model,
            court=case.court,
            topic=case.topic,
            runtime="Direct",
        )
    async with agent:
        handle = await agent.run(message=case.question)
        async for event in handle.events():
            payload = event.payload.model_dump(mode="json")
            emit(payload)
            if payload["type"] == "question":
                raise RuntimeError(
                    "Agent requested input in a single-turn case."
                )
        outcome = await handle.result()
        if outcome.state != "completed":
            raise RuntimeError(f"Agent ended in state {outcome.state}.")
        return {"outcome": outcome.model_dump(mode="json")}


def invoke(system, case, model, identity, emit, resource_root=None):
    if system == "raw":
        return asyncio.run(raw(case.question, model, emit))
    if system == "old":
        return old(case, model, identity, emit)
    if system == "new":
        return asyncio.run(new(case, model, identity, emit, resource_root))
    raise ValueError(f"Unknown system: {system}")
