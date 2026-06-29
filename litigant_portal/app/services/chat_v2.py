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

logger = logging.getLogger(__name__)

MAX_STEPS = 30


def chat_thread_delete(*, identity: UserIdentity, thread_id: str) -> None:
    """Delete a thread (and its messages, via cascade) owned by the identity."""
    chat_thread_get(identity=identity, thread_id=thread_id).delete()


def _resolve_thread(
    *, identity: UserIdentity, thread_id: str | None
) -> ChatThread:
    """Return the identity's thread, creating a fresh one when no id is given."""
    if thread_id:
        return ChatThread.objects.get(id=thread_id, identity=identity)
    return ChatThread.objects.create(identity=identity)


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
    system_prompt: str, history: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Prepend the (never-stored) system prompt and project to litellm shape."""
    return [
        {"role": "system", "content": system_prompt},
        *(_to_llm_message(m) for m in history),
    ]


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
    messages = [dict(m.data) for m in chat_message_list(thread=thread)]
    results = {
        m.get("tool_call_id"): m for m in messages if m.get("role") == "tool"
    }

    items: list[dict[str, Any]] = []
    for msg in messages:
        role = msg.get("role")
        if role == "user":
            items.append({"kind": "user", "content": msg.get("content", "")})
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
    thread_id: str | None = None,
) -> StreamingHttpResponse:
    """Stream an agent's reply for ``message``, running the tool loop."""
    thread = _resolve_thread(identity=identity, thread_id=thread_id)
    agent = agent_class()

    ChatMessage.objects.create(
        thread=thread, data={"role": "user", "content": message}
    )

    history: list[dict[str, Any]] = [
        dict(m.data) for m in chat_message_list(thread=thread)
    ]

    def event_stream() -> Iterator[str]:
        yield _sse({"type": "thread", "thread_id": str(thread.id)})

        try:
            system_prompt = agent.generate_system_prompt(thread_id=thread.id)

            for _ in range(MAX_STEPS):
                call_args: dict[str, Any] = {
                    **agent.completion_args,
                    "messages": _messages_for_llm(system_prompt, history),
                    "stream": True,
                }
                if agent.tool_schemas:
                    call_args["tools"] = agent.tool_schemas

                content_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []

                for chunk in litellm.completion(**call_args):
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
                ChatMessage.objects.create(thread=thread, data=assistant_msg)

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
                    ChatMessage.objects.create(thread=thread, data=tool_msg)

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
