from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from .agents import agent_registry
from .services.chat_service import ChatService
from .services.search_service import search_service


@require_POST
@ratelimit(key="ip", rate="20/m", method="POST", block=True)
def stream(request: HttpRequest):
    """
    Send a message and stream the AI response.

    POST body:
        message: The user's message (required)
        session_id: Optional session ID to continue a conversation
        agent_name: Optional agent name to use (defaults to DEFAULT_CHAT_AGENT)

    Returns SSE stream with events:
        - session: {type: "session", session_id: "..."} (first event)
        - content_delta: {type: "content_delta", content: "..."}
        - tool_call: {type: "tool_call", id: "...", name: "...", args: {...}}
        - tool_response: {type: "tool_response", id: "...", name: "...", data: {...}}
        - done: {type: "done"}
        - error: {type: "error", error: "..."}
    """
    message = request.POST.get("message", "").strip()
    session_id = request.POST.get("session_id") or None
    agent_name = request.POST.get("agent_name") or None

    if not message:
        return JsonResponse({"error": "Message is required"}, status=400)

    if len(message) > 2000:
        return JsonResponse(
            {"error": "Message is too long (max 2000 characters)"}, status=400
        )

    try:
        chat = ChatService(
            request, session_id=session_id, agent_name=agent_name
        )
        return chat.stream(message)
    except PermissionError:
        return JsonResponse({"error": "Unauthorized"}, status=403)
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=404)


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def search(request: HttpRequest):
    """
    Keyword search endpoint.

    Used when AI chat is unavailable or disabled.
    """
    query = request.GET.get("q", "").strip()
    category = request.GET.get("category")

    if not query:
        return render(
            request,
            "chat/partials/_search_results.html",
            {"results": [], "query": ""},
        )

    results = search_service.search(query, category=category, limit=10)

    return render(
        request,
        "chat/partials/_search_results.html",
        {
            "results": results,
            "query": query,
            "category": category,
        },
    )


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def status(request: HttpRequest) -> JsonResponse:
    """Check if chat service is available."""
    available = False
    if getattr(settings, "CHAT_ENABLED", True):
        agent_name = settings.DEFAULT_CHAT_AGENT
        if agent_name in agent_registry:
            available = agent_registry[agent_name]().ping()

    return JsonResponse(
        {
            "enabled": getattr(settings, "CHAT_ENABLED", True),
            "available": available,
        }
    )
