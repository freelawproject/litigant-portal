from uuid import UUID

from django.http import HttpRequest, JsonResponse
from django.utils.translation import gettext as _

from litigant_portal.agents.base import Agent
from litigant_portal.app.models import ChatThread, UserUpload
from litigant_portal.app.selectors.chat_engine import (
    chat_thread_get,
    chat_thread_list,
    chat_thread_usage,
)
from litigant_portal.app.services.chat_engine import (
    chat_stream,
    chat_thread_delete,
    thread_render_items,
)


def stream(
    request: HttpRequest,
    *,
    agent_class: type[Agent],
    thread_type: str,
    model: str,
):
    """Stream an agent reply for a message within a thread."""
    message = request.POST.get("message", "").strip()
    thread_id = request.POST.get("thread_id") or None
    attachment_ids = request.POST.getlist("attachment_ids")

    if not message:
        return JsonResponse({"error": _("Message is required")}, status=400)

    if attachment_ids:
        try:
            attachment_ids = list(
                dict.fromkeys(str(UUID(i)) for i in attachment_ids)
            )
        except ValueError:
            return JsonResponse({"error": _("Invalid attachment")}, status=400)
        owned = UserUpload.objects.filter(
            identity=request.identity, id__in=attachment_ids
        ).count()
        if owned != len(attachment_ids):
            return JsonResponse({"error": _("Invalid attachment")}, status=400)

    try:
        return chat_stream(
            identity=request.identity,
            message=message,
            thread_id=thread_id,
            attachment_ids=attachment_ids or None,
            agent_class=agent_class,
            thread_type=thread_type,
            model=model,
        )
    except ChatThread.DoesNotExist:
        return JsonResponse({"error": _("Thread not found")}, status=404)


def thread_list(request: HttpRequest, *, thread_type: str) -> JsonResponse:
    """List the identity's threads for this surface."""
    threads = [
        {
            "id": str(thread.id),
            "description": thread.description,
            "snippet": (thread.snippet or "")[:500],
            "last_at": (
                thread.last_message_at or thread.updated_at
            ).isoformat(),
        }
        for thread in chat_thread_list(
            identity=request.identity, thread_type=thread_type
        )
    ]
    return JsonResponse({"threads": threads})


def message_list(
    request: HttpRequest,
    thread_id,
    *,
    agent_class: type[Agent],
    thread_type: str,
) -> JsonResponse:
    """Load a thread's messages and state so the frontend can render it."""
    try:
        thread = chat_thread_get(
            identity=request.identity,
            thread_id=thread_id,
            thread_type=thread_type,
        )
    except ChatThread.DoesNotExist:
        return JsonResponse({"error": _("Thread not found")}, status=404)

    return JsonResponse(
        {
            "id": str(thread.id),
            "description": thread.description,
            "items": thread_render_items(
                thread=thread, agent_class=agent_class
            ),
            "state": thread.state,
        }
    )


def thread_usage(
    request: HttpRequest, thread_id, *, thread_type: str
) -> JsonResponse:
    """Total tokens and cost for a thread."""
    try:
        thread = chat_thread_get(
            identity=request.identity,
            thread_id=thread_id,
            thread_type=thread_type,
        )
    except ChatThread.DoesNotExist:
        return JsonResponse({"error": _("Thread not found")}, status=404)

    return JsonResponse(chat_thread_usage(thread=thread))


def thread_delete(
    request: HttpRequest, thread_id, *, thread_type: str
) -> JsonResponse:
    """Delete a thread (and its messages) owned by the current identity."""
    try:
        chat_thread_delete(
            identity=request.identity,
            thread_id=thread_id,
            thread_type=thread_type,
        )
    except ChatThread.DoesNotExist:
        return JsonResponse({"error": _("Thread not found")}, status=404)
    return JsonResponse({"deleted": True})
