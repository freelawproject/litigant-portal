import json
import uuid

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from .services.chat_service import chat_service
from .services.extraction_service import extraction_service
from .services.pdf_service import pdf_service
from .services.search_service import search_service


@require_POST
@ratelimit(key="ip", rate="20/m", method="POST", block=True)
def send_message(request: HttpRequest) -> JsonResponse:
    """
    Handle a new chat message from the user.

    Creates the message and returns the session ID for streaming.
    Rate limited to 20 requests per minute per IP.
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
@ratelimit(key="ip", rate="20/m", method="GET", block=True)
def stream_response(request: HttpRequest, session_id: uuid.UUID):
    """
    Stream the AI response as Server-Sent Events.

    This endpoint is called after send_message to receive the
    streaming response from the AI provider.
    Rate limited to 20 requests per minute per IP.
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
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def keyword_search(request: HttpRequest):
    """
    Fallback keyword search endpoint.

    Used when AI chat is unavailable or disabled.
    Rate limited to 60 requests per minute per IP.
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
def chat_status(request: HttpRequest) -> JsonResponse:
    """
    Check if chat service is available.

    Returns the current status of the AI chat service.
    Rate limited to 60 requests per minute per IP.
    """
    return JsonResponse(
        {
            "enabled": settings.CHAT_ENABLED,
            "available": chat_service.is_available(),
            "provider": settings.CHAT_PROVIDER,
        }
    )


@require_POST
@ratelimit(key="ip", rate="10/m", method="POST", block=True)
def upload_document(request: HttpRequest) -> JsonResponse:
    """
    Handle PDF document upload, text extraction, and LLM analysis.

    Extracts text from uploaded PDF files and uses LLM to extract
    structured case information.
    In-memory processing only - no file storage.
    Rate limited to 10 requests per minute per IP.
    """
    if "file" not in request.FILES:
        return JsonResponse({"error": "No file uploaded"}, status=400)

    uploaded_file = request.FILES["file"]

    # Extract text from PDF
    pdf_result = pdf_service.extract_text(uploaded_file)

    if not pdf_result.success:
        return JsonResponse({"error": pdf_result.error}, status=400)

    # Extract structured data using LLM
    extraction_result = extraction_service.extract_from_text(pdf_result.text)

    if not extraction_result.success:
        # Return partial success - text extracted but analysis failed
        return JsonResponse(
            {
                "success": True,
                "page_count": pdf_result.page_count,
                "text_preview": pdf_result.text_preview,
                "extracted_data": None,
                "extraction_error": extraction_result.error,
            }
        )

    return JsonResponse(
        {
            "success": True,
            "page_count": pdf_result.page_count,
            "text_preview": pdf_result.text_preview,
            "extracted_data": extraction_result.to_dict(),
        }
    )


@require_POST
@ratelimit(key="ip", rate="10/m", method="POST", block=True)
def summarize_conversation(request: HttpRequest) -> JsonResponse:
    """
    Generate a summary of a conversation.

    Accepts a list of messages and returns an LLM-generated summary.
    Rate limited to 10 requests per minute per IP.
    """
    messages_raw = request.POST.get("messages", "")

    if not messages_raw:
        return JsonResponse({"error": "Messages are required"}, status=400)

    try:
        messages = json.loads(messages_raw)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid messages format"}, status=400)

    if not isinstance(messages, list) or len(messages) < 2:
        return JsonResponse(
            {"error": "At least 2 messages required for summary"}, status=400
        )

    summary = chat_service.generate_summary(messages)

    if summary is None:
        return JsonResponse(
            {"error": "Failed to generate summary"}, status=500
        )

    return JsonResponse({"summary": summary})


@require_POST
@ratelimit(key="ip", rate="10/m", method="POST", block=True)
def clear_session(request: HttpRequest) -> JsonResponse:
    """
    Clear the current user's chat session and all messages.

    For authenticated users, deletes their session.
    For anonymous users, deletes session by session_key.
    Rate limited to 10 requests per minute per IP.
    """
    from .models import ChatSession

    deleted_count = 0

    if request.user.is_authenticated:
        deleted_count, _ = ChatSession.objects.filter(user=request.user).delete()
    else:
        session_key = request.session.session_key
        if session_key:
            deleted_count, _ = ChatSession.objects.filter(
                session_key=session_key
            ).delete()

    return JsonResponse({"success": True, "deleted": deleted_count})
