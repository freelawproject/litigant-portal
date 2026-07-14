import json
import logging
from collections.abc import Iterator
from typing import Any

import litellm
from django.http import StreamingHttpResponse
from django.template.loader import render_to_string

from litigant_portal.agents_v2.base import Agent, ToolOutput
from litigant_portal.app.models import ChatMessage, ChatThread, UserIdentity
from litigant_portal.app.selectors.chat_v2 import (
    chat_message_list,
    chat_thread_get,
)
from litigant_portal.app.services.assistant import attachment_render_list
from litigant_portal.app.services.attachments import (
    attachments_for_llm,
)
from litigant_portal.settings import CHAT_MODEL

logger = logging.getLogger(__name__)

MAX_STEPS = 30

DESCRIPTION_PROMPT = (
    "Write a very short title (at most 6 words) for the following "
    "conversation. Return only the title — no quotes, no trailing "
    "punctuation."
)


def chat_message_create(
    *,
    thread_id,
    data: dict,
    model: str,
    num_tokens: int | None = None,
    hidden: bool = False,
    meta: bool = False,
    cost: float = 0.0,
) -> ChatMessage:
    """Add a message to a thread."""
    if num_tokens is None:
        num_tokens = litellm.token_counter(
            model=model, text=data.get("content", "")
        )
    return ChatMessage.objects.create(
        thread_id=thread_id,
        data=data,
        hidden=hidden,
        meta=meta,
        num_tokens=num_tokens,
        cost=cost,
    )


def chat_thread_delete(
    *, identity: UserIdentity, thread_id: str, thread_type: str
) -> None:
    """Delete a thread (and its messages, via cascade) owned by the identity."""
    chat_thread_get(
        identity=identity, thread_id=thread_id, thread_type=thread_type
    ).delete()


def chat_message_inject_hidden(
    *, thread_id, content: str, model: str, role: str = "user"
) -> ChatMessage:
    """Append a hidden message to a thread's history."""
    return chat_message_create(
        thread_id=thread_id,
        data={"role": role, "content": content},
        model=model,
        hidden=True,
    )


def chat_message_inject_meta(
    *,
    thread_id,
    kind: str,
    model: str,
    num_tokens: int = 0,
    cost: float = 0.0,
) -> ChatMessage:
    """Append an accounting-only meta message to a thread — invisible to the
    LLM and the frontend, counted by chat_thread_usage."""
    return chat_message_create(
        thread_id=thread_id,
        data={"role": "meta", "kind": kind},
        model=model,
        num_tokens=num_tokens,
        meta=True,
        cost=cost,
    )


def chat_thread_generate_description(*, thread: ChatThread) -> str:
    """Generate and store a short description of a thread's conversation."""
    conversation = "\n".join(
        f"{m.data.get('role')}: {m.data.get('content')}"
        for m in chat_message_list(
            thread=thread, exclude_hidden=True, exclude_meta=True
        )
        if m.data.get("role") in ("user", "assistant")
        and m.data.get("content")
    )
    response = litellm.completion(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": DESCRIPTION_PROMPT},
            {"role": "user", "content": conversation[:4000]},
        ],
    )
    try:
        cost = litellm.completion_cost(completion_response=response)
    except Exception:
        cost = 0.0
    usage = getattr(response, "usage", None)
    # Book the call's tokens/cost so chat_thread_usage reflects it.
    chat_message_inject_meta(
        thread_id=thread.id,
        kind="thread_description",
        model=CHAT_MODEL,
        num_tokens=usage.total_tokens if usage else 0,
        cost=cost,
    )
    description = (response.choices[0].message.content or "").strip()[:255]
    if description:
        thread.description = description
        thread.save(update_fields=["description", "updated_at"])
    return description


def _resolve_thread(
    *, identity: UserIdentity, thread_id: str | None, thread_type: str
) -> ChatThread:
    """Return the identity's thread, creating a fresh one when no id is given."""
    if thread_id:
        return chat_thread_get(
            identity=identity, thread_id=thread_id, thread_type=thread_type
        )
    return ChatThread.objects.create(
        identity=identity, thread_type=thread_type
    )


def _sse(payload: dict[str, Any]) -> str:
    """Serialize a payload as a single SSE ``data:`` frame."""
    return f"data: {json.dumps(payload)}\n\n"


def _to_llm_message(msg: dict[str, Any]) -> dict[str, Any]:
    """Project a stored message onto the exact litellm message shape."""
    role = msg.get("role")
    if role == "tool":
        return {
            "role": "tool",
            "tool_call_id": msg.get("tool_call_id"),
            "name": msg.get("name"),
            "content": msg.get("content", ""),
        }
    if role == "assistant":
        out: dict[str, Any] = {
            "role": "assistant",
            "content": msg.get("content", ""),
        }
        if msg.get("tool_calls"):
            out["tool_calls"] = msg["tool_calls"]
        return out
    return {"role": "user", "content": msg.get("content", "")}


def _messages_for_llm(
    system_prompt: str,
    history: list[dict[str, Any]],
    *,
    model: str,
    attachment_cache: dict,
) -> list[dict[str, Any]]:
    """Prepend the (never-stored) system prompt and project to litellm shape,
    and inject attachment content parts or stubs."""
    hydrated = attachments_for_llm(
        history=history, model=model, cache=attachment_cache
    )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt}
    ]
    for i, msg in enumerate(history):
        llm_msg = _to_llm_message(msg)
        if i in hydrated:
            llm_msg["content"] = hydrated[i]
        messages.append(llm_msg)
    return messages


def _render_tool(template: str | bool | None, context: dict) -> dict[str, Any]:
    """Resolve a tool's render template into a frontend rendering directive."""
    if template is False:
        return {"render_mode": "skip"}
    if template is None:
        return {"render_mode": "default"}
    return {
        "render_mode": "custom",
        "render_html": render_to_string(template, context),
    }


def _tool_item(tool_call: dict, results: dict, tools: dict) -> dict[str, Any]:
    """Build a frontend tool descriptor from a stored assistant tool call."""
    fn = tool_call.get("function", {})
    name = fn.get("name", "")
    tool_id = tool_call.get("id") or ""
    try:
        args = json.loads(fn.get("arguments") or "{}")
    except json.JSONDecodeError:
        args = {}

    tool_class = tools.get(name)
    render_data = (results.get(tool_id) or {}).get("data")

    if tool_class is not None:
        call = _render_tool(tool_class.tool_call_template, {"args": args})
        result = _render_tool(
            tool_class.tool_result_template, {"data": render_data or {}}
        )
    else:
        call = {"render_mode": "default"}
        result = {"render_mode": "default"}

    return {
        "kind": "tool",
        "id": tool_id,
        "name": name,
        "args": args,
        "render_data": render_data,
        "call_render_mode": call["render_mode"],
        "call_render_html": call.get("render_html", ""),
        "result_render_mode": result["render_mode"],
        "result_render_html": result.get("render_html", ""),
    }


def thread_render_items(
    *, thread: ChatThread, agent_class: type[Agent]
) -> list[dict[str, Any]]:
    """Project a thread's stored messages into frontend render items."""
    agent = agent_class()
    tools = agent.tools_by_name
    messages = [
        dict(m.data)
        for m in chat_message_list(
            thread=thread, exclude_hidden=True, exclude_meta=True
        )
    ]
    results = {
        m.get("tool_call_id"): m for m in messages if m.get("role") == "tool"
    }

    items: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "user":
            item: dict[str, Any] = {
                "kind": "user",
                "content": msg.get("content", ""),
            }
            if msg.get("attachments"):
                item["attachments"] = attachment_render_list(
                    msg["attachments"]
                )
            items.append(item)
        elif role == "assistant":
            content = msg.get("content", "")
            if content:
                items.append({"kind": "assistant", "content": content})
            for tool_call in msg.get("tool_calls") or []:
                items.append(_tool_item(tool_call, results, tools))
    return items


def _execute_tool(
    *, tool_class, args: dict, thread_id, name: str
) -> ToolOutput:
    """Run a tool, normalizing unknown tools and errors into a ToolOutput."""
    try:
        if tool_class is None:
            raise ValueError(f"Unknown tool: {name}")
        return tool_class(**args)(thread_id=thread_id)
    except Exception as e:
        logger.exception("chat_v2 tool %s failed", name)
        return ToolOutput(result=f"Error: {e}")


def chat_stream(
    *,
    identity: UserIdentity,
    message: str,
    agent_class: type[Agent],
    thread_type: str,
    model: str,
    thread_id: str | None = None,
    attachment_ids: list[str] | None = None,
) -> StreamingHttpResponse:
    """Stream an agent's reply for ``message``, running the tool loop."""
    thread = _resolve_thread(
        identity=identity, thread_id=thread_id, thread_type=thread_type
    )
    agent = agent_class()

    if "model" in agent.completion_args:
        raise ValueError(
            f"{agent_class.__name__}.completion_args must not set 'model' — "
            "the model is passed to chat_stream by the caller."
        )

    user_data: dict[str, Any] = {"role": "user", "content": message}
    if attachment_ids:
        user_data["attachments"] = [str(i) for i in attachment_ids]
    chat_message_create(
        thread_id=thread.id,
        data=user_data,
        model=model,
    )

    history: list[dict[str, Any]] = [
        dict(m.data)
        for m in chat_message_list(thread=thread, exclude_meta=True)
    ]

    def event_stream() -> Iterator[str]:
        yield _sse({"type": "thread", "thread_id": str(thread.id)})

        attachment_cache: dict = {}

        try:
            system_prompt = agent.generate_system_prompt(thread_id=thread.id)

            for _ in range(MAX_STEPS):
                call_args: dict[str, Any] = {
                    **agent.completion_args,
                    "model": model,
                    "messages": _messages_for_llm(
                        system_prompt,
                        history,
                        model=model,
                        attachment_cache=attachment_cache,
                    ),
                    "stream": True,
                    "stream_options": {"include_usage": True},
                }
                if agent.tool_schemas:
                    call_args["tools"] = agent.tool_schemas

                content_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []
                cost = 0.0
                completion_tokens = None

                for chunk in litellm.completion(**call_args):
                    usage = getattr(chunk, "usage", None)
                    if usage:
                        try:
                            cost = litellm.completion_cost(
                                completion_response=chunk, model=model
                            )
                            completion_tokens = usage.completion_tokens
                        except Exception:
                            logger.exception(
                                "Chat cost/usage extraction failed (model=%s)",
                                model,
                            )
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta

                    if delta.content:
                        content_parts.append(delta.content)
                        yield _sse(
                            {
                                "type": "content_delta",
                                "content": delta.content,
                            }
                        )

                    for tc in delta.tool_calls or []:
                        while tc.index >= len(tool_calls):
                            tool_calls.append(
                                {
                                    "id": None,
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            )
                        slot = tool_calls[tc.index]
                        if tc.id:
                            slot["id"] = tc.id
                        if tc.function and tc.function.name:
                            slot["function"]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            slot["function"]["arguments"] += (
                                tc.function.arguments
                            )

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": "".join(content_parts),
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                history.append(assistant_msg)
                chat_message_create(
                    thread_id=thread.id,
                    data=assistant_msg,
                    model=model,
                    num_tokens=completion_tokens,
                    cost=cost,
                )

                if not tool_calls:
                    break

                refresh = False
                for tool_call in tool_calls:
                    fn = tool_call.get("function", {})
                    name = fn.get("name", "")
                    tool_id = tool_call.get("id") or ""
                    try:
                        args = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        args = {}
                    tool_class = agent.tools_by_name.get(name)

                    yield _sse(
                        {
                            "type": "tool_call",
                            "id": tool_id,
                            "name": name,
                            "args": args,
                            **(
                                _render_tool(
                                    tool_class.tool_call_template,
                                    {"args": args},
                                )
                                if tool_class is not None
                                else {"render_mode": "default"}
                            ),
                        }
                    )

                    output = _execute_tool(
                        tool_class=tool_class,
                        args=args,
                        thread_id=thread.id,
                        name=name,
                    )
                    refresh = refresh or output.refresh_system_prompt

                    tool_msg: dict[str, Any] = {
                        "role": "tool",
                        "tool_call_id": tool_id,
                        "name": name,
                        "content": output.result,
                    }
                    if output.render_data is not None:
                        tool_msg["data"] = output.render_data
                    history.append(tool_msg)
                    chat_message_create(
                        thread_id=thread.id,
                        data=tool_msg,
                        model=model,
                        cost=output.cost,
                    )

                    yield _sse(
                        {
                            "type": "tool_response",
                            "id": tool_id,
                            "name": name,
                            "render_data": output.render_data,
                            **(
                                _render_tool(
                                    tool_class.tool_result_template,
                                    {"data": output.render_data or {}},
                                )
                                if tool_class is not None
                                else {"render_mode": "default"}
                            ),
                        }
                    )

                thread.refresh_from_db(fields=["state"])
                yield _sse({"type": "state", "state": thread.state})

                if refresh:
                    system_prompt = agent.generate_system_prompt(
                        thread_id=thread.id
                    )

            if not thread.description:
                try:
                    description = chat_thread_generate_description(
                        thread=thread
                    )
                    if description:
                        yield _sse(
                            {
                                "type": "description",
                                "description": description,
                            }
                        )
                except Exception:
                    logger.exception("chat_v2 description generation failed")

            thread.save(update_fields=["updated_at"])
            yield _sse({"type": "done"})
        except Exception as e:
            logger.exception("chat_v2 stream failed")
            yield _sse({"type": "error", "error": str(e)})
            yield _sse({"type": "done"})

    response = StreamingHttpResponse(
        event_stream(), content_type="text/event-stream"
    )
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
