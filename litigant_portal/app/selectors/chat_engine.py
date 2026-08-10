from django.db.models import OuterRef, QuerySet, Subquery, Sum

from litigant_portal.app.models import ChatMessage, ChatThread, UserIdentity


def chat_thread_list(
    *, identity: UserIdentity, thread_type: str
) -> QuerySet[ChatThread]:
    """An identity's threads for a given thread type."""
    visible = ChatMessage.objects.filter(
        thread=OuterRef("pk"), hidden=False, meta=False
    ).order_by("-created_at")
    snippet_source = visible.filter(
        data__role__in=["user", "assistant"]
    ).exclude(data__content="")
    return (
        ChatThread.objects.filter(identity=identity, thread_type=thread_type)
        .annotate(
            last_message_at=Subquery(visible.values("created_at")[:1]),
            snippet=Subquery(snippet_source.values("data__content")[:1]),
        )
        .order_by("-updated_at")
    )


def chat_thread_get(
    *, identity: UserIdentity, thread_id, thread_type: str
) -> ChatThread:
    """A single thread scoped by identity and thread type."""
    return ChatThread.objects.get(
        id=thread_id, identity=identity, thread_type=thread_type
    )


def chat_message_list(
    *,
    thread: ChatThread,
    exclude_hidden: bool = False,
    exclude_meta: bool = False,
) -> QuerySet[ChatMessage]:
    """A thread's messages, oldest first. The unfiltered default is the
    accounting view (usage sums everything); exclude_meta gives the LLM
    history; exclude_hidden + exclude_meta gives the frontend render view."""
    messages = thread.messages.order_by("created_at")
    if exclude_hidden:
        messages = messages.filter(hidden=False)
    if exclude_meta:
        messages = messages.filter(meta=False)
    return messages


def chat_thread_owner_label(*, thread: ChatThread) -> str:
    """The review label for a thread's owner: email or session key."""
    identity = thread.identity
    if identity.user_id:
        return identity.user.email or identity.user.username
    return f"anonymous (session {identity.session_key})"


def chat_thread_export_data(*, thread: ChatThread) -> dict:
    """Full-fidelity audit export: thread metadata plus every message row.

    Built from raw ChatMessage.data with hidden and meta rows included. The
    frontend render path (thread_render_items) is lossy and unsuitable here.
    """
    identity = thread.identity
    return {
        "thread_id": str(thread.id),
        "thread_type": thread.thread_type,
        "description": thread.description,
        "created_at": thread.created_at.isoformat(),
        "updated_at": thread.updated_at.isoformat(),
        "owner": {
            "user_email": identity.user.email if identity.user_id else None,
            "session_key": identity.session_key,
        },
        "messages": [
            {
                "id": str(m.id),
                "created_at": m.created_at.isoformat(),
                "hidden": m.hidden,
                "meta": m.meta,
                "num_tokens": m.num_tokens,
                "cost": m.cost,
                "data": dict(m.data),
            }
            for m in chat_message_list(thread=thread)
        ],
    }


def chat_thread_export_markdown(*, thread: ChatThread) -> str:
    """Human-readable audit transcript of every message row."""
    export = chat_thread_export_data(thread=thread)
    lines = [
        f"# Chat transcript {export['thread_id']}",
        "",
        f"- Owner: {chat_thread_owner_label(thread=thread)}",
        f"- Started: {export['created_at']}",
        f"- Description: {export['description'] or '(none)'}",
    ]
    for msg in export["messages"]:
        lines.append("")
        lines.extend(_message_lines(msg))
    return "\n".join(lines) + "\n"


def _message_lines(msg: dict) -> list[str]:
    data = msg["data"]
    role = data.get("role", "unknown")
    heading = role
    if role == "tool":
        heading = f"tool result: {data.get('name', 'unknown')}"
    elif role == "meta":
        heading = f"meta: {data.get('kind', 'unknown')}"
    flags = [flag for flag in ("hidden", "meta") if msg[flag]]
    if flags:
        heading += " [" + ", ".join(flags) + "]"
    lines = [f"## {heading} ({msg['created_at']})"]
    if data.get("content"):
        lines += ["", data["content"]]
    for call in data.get("tool_calls") or []:
        function = call.get("function", {})
        name = function.get("name", "unknown")
        lines += ["", f"Tool call: {name}({function.get('arguments', '')})"]
    if data.get("attachments"):
        lines += ["", f"Attachments: {', '.join(data['attachments'])}"]
    if role == "meta":
        lines += [
            "",
            f"(accounting only: {msg['num_tokens']} tokens, cost {msg['cost']})",
        ]
    return lines


def chat_thread_usage(*, thread: ChatThread) -> dict:
    """Total tokens and cost across all of a thread's messages (incl.
    hidden and meta)."""
    totals = chat_message_list(thread=thread).aggregate(
        total_tokens=Sum("num_tokens"), total_cost=Sum("cost")
    )
    return {
        "total_tokens": totals["total_tokens"] or 0,
        "total_cost": totals["total_cost"] or 0.0,
    }
