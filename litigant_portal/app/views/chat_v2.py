from django.http import HttpRequest, JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from litigant_portal.agents_v2 import WeatherAgent
from litigant_portal.app.models import ChatThread
from litigant_portal.app.selectors.chat_v2 import (
    chat_message_list,
    chat_thread_get,
    chat_thread_list,
)
from litigant_portal.app.services.chat_v2 import (
    chat_stream as chat_stream_service,
)
from litigant_portal.app.services.chat_v2 import (
    chat_thread_delete,
    thread_render_items,
)


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def thread_list(request: HttpRequest) -> JsonResponse:
    """List the current identity's chat threads."""
    threads = []
    for thread in chat_thread_list(identity=request.identity):
        messages = list(chat_message_list(thread=thread))
        last = messages[-1] if messages else None
        snippet = next(
            (
                m.data.get("content", "")
                for m in reversed(messages)
                if m.data.get("role") in ("user", "assistant")
                and m.data.get("content")
            ),
            "",
        )
        threads.append(
            {
                "id": str(thread.id),
                "snippet": snippet,
                "last_at": (
                    last.created_at if last else thread.updated_at
                ).isoformat(),
            }
        )
    return JsonResponse({"threads": threads})


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def message_list(request: HttpRequest, thread_id) -> JsonResponse:
    """Load a thread's messages and state so the sidebar can load it."""
    try:
        thread = chat_thread_get(
            identity=request.identity, thread_id=thread_id
        )
    except ChatThread.DoesNotExist:
        return JsonResponse({"error": _("Thread not found")}, status=404)

    return JsonResponse(
        {
            "id": str(thread.id),
            "items": thread_render_items(
                thread=thread, agent_class=WeatherAgent
            ),
            "state": thread.state,
        }
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def thread_delete(request: HttpRequest, thread_id) -> JsonResponse:
    """Delete a thread (and its messages) owned by the current identity."""
    try:
        chat_thread_delete(identity=request.identity, thread_id=thread_id)
    except ChatThread.DoesNotExist:
        return JsonResponse({"error": _("Thread not found")}, status=404)
    return JsonResponse({"deleted": True})


@require_POST
@ratelimit(key="ip", rate="20/m", method="POST", block=True)
def chat_stream(request: HttpRequest):
    """Stream an assistant reply for a message within a chat thread."""
    message = request.POST.get("message", "").strip()
    thread_id = request.POST.get("thread_id") or None

    if not message:
        return JsonResponse({"error": _("Message is required")}, status=400)

    try:
        return chat_stream_service(
            identity=request.identity,
            message=message,
            thread_id=thread_id,
            agent_class=WeatherAgent,
        )
    except ChatThread.DoesNotExist:
        return JsonResponse({"error": _("Thread not found")}, status=404)
