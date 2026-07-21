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
