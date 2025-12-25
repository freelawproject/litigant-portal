import uuid

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .services.chat_service import chat_service
from .services.search_service import search_service


@require_POST
def send_message(request: HttpRequest) -> JsonResponse:
    """
    Handle a new chat message from the user.

    Creates the message and returns the session ID for streaming.
    """
    content = request.POST.get("message", "").strip()

    if not content:
        return JsonResponse({"error": "Message is required"}, status=400)

    if len(content) > 2000:
        return JsonResponse(
            {"error": "Message is too long (max 2000 characters)"}, status=400
        )

    session = chat_service.get_or_create_session(request)
    message = chat_service.add_user_message(session, content)

    return JsonResponse(
        {
            "session_id": str(session.id),
            "message_id": str(message.id),
        }
    )


@require_GET
def stream_response(request: HttpRequest, session_id: uuid.UUID):
    """
    Stream the AI response as Server-Sent Events.

    This endpoint is called after send_message to receive the
    streaming response from the AI provider.
    """
    session = chat_service.get_session(str(session_id))

    if session is None:
        return JsonResponse({"error": "Session not found"}, status=404)

    # Verify session ownership (user or session key match)
    if request.user.is_authenticated:
        if session.user != request.user:
            return JsonResponse({"error": "Unauthorized"}, status=403)
    else:
        if session.session_key != request.session.session_key:
            return JsonResponse({"error": "Unauthorized"}, status=403)

    return chat_service.stream_response(session)


@require_GET
def keyword_search(request: HttpRequest):
    """
    Fallback keyword search endpoint.

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
def chat_status(request: HttpRequest) -> JsonResponse:
    """
    Check if chat service is available.

    Returns the current status of the AI chat service.
    """
    return JsonResponse(
        {
            "enabled": settings.CHAT_ENABLED,
            "available": chat_service.is_available(),
            "provider": settings.CHAT_PROVIDER,
        }
    )
