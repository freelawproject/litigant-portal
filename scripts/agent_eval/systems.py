"""
Thin adapters around the raw provider and unchanged application entry points.
"""

import asyncio
import json
import os

from .provider import close_stream, data
from .schema import normalize_system


def turns(case, emit):
    """
    Yield ``(message, on_text)`` for each user turn of a case.

    History turns collect their reply locally and publish it as one ``turn``
    event; only the final question streams into the graded answer. The
    returned list fills with ``{"user", "assistant"}`` pairs as turns finish.
    """
    transcript = []

    def run():
        for message in case.history:
            reply = []
            yield message, reply.append
            transcript.append({"user": message, "assistant": "".join(reply)})
            emit({"type": "turn", **transcript[-1]})
        yield (
            case.question,
            lambda delta: emit({"type": "text", "delta": delta}),
        )

    return transcript, run()


async def raw(case, model: str, emit) -> dict:
    """
    Send exactly the user turns, without an instruction or system message.
    """
    transcript, sequence = turns(case, emit)
    messages = []
    for message, on_text in sequence:
        messages.append({"role": "user", "content": message})
        reply = await _raw_turn(messages, model, on_text)
        messages.append({"role": "assistant", "content": reply})
    return {"provider_status": "completed", "transcript": transcript}


async def _raw_turn(messages: list[dict], model: str, on_text) -> str:
    import litellm
    from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler

    client = AsyncHTTPHandler()
    reply = []
    try:
        stream = await litellm.aresponses(
            model=model,
            input=messages,
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
                    reply.append(event["delta"])
                    on_text(event["delta"])
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
        return "".join(reply)
    finally:
        await client.close()


def current(case, model: str, identity, emit) -> dict:
    from litigant_portal.agents.assistant import LitigantAssistant
    from litigant_portal.app.models import ChatThread
    from litigant_portal.app.selectors.chat_engine import (
        chat_thread_export_data,
    )
    from litigant_portal.app.services.chat_engine import chat_stream

    # Stored facts persist per identity, so a case must not inherit what an
    # earlier case's user said. Rows are those of the evaluation identity.
    identity.variable_answers.all().delete()
    transcript, sequence = turns(case, emit)
    thread_id = None
    for message, on_text in sequence:
        response = chat_stream(
            identity=identity,
            message=message,
            agent_class=LitigantAssistant,
            thread_type="user_chat",
            model=model,
            thread_id=thread_id,
        )
        error, done = None, False
        try:
            for frame in response:
                text = frame.decode() if isinstance(frame, bytes) else frame
                event = json.loads(text.removeprefix("data: ").strip())
                kind = event["type"]
                if kind == "thread":
                    thread_id = event["thread_id"]
                elif kind == "content_delta":
                    on_text(event["content"])
                    continue
                elif kind == "error":
                    error = (
                        event.get("message")
                        or event.get("error")
                        or "Current agent reported a stream error."
                    )
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
                error or "Current agent stopped without a final answer."
            )
    return {
        "thread_id": thread_id,
        "thread_export": export,
        "transcript": transcript,
        "stored_facts": [
            {"name": a.variable.name, "value": a.value}
            for a in identity.variable_answers.select_related("variable")
        ],
        "corpus_load_observed": any(
            message.get("name") == "LoadTopicFlow"
            and message.get("content", "").startswith(
                "The active topic flow is now "
            )
            for message in messages
            if message.get("role") == "tool"
        ),
    }


def invoke(system, case, model, identity, emit):
    system = normalize_system(system)
    if system == "raw":
        return asyncio.run(raw(case, model, emit))
    return current(case, model, identity, emit)
