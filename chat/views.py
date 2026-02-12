import json

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from .agents import agent_registry
from .services.chat_service import ChatService
from .services.pdf_service import pdf_service
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
    agent = agent_registry["DocumentExtractionAgent"]()
    print(pdf_result.text)
    result = agent(pdf_result.text)

    if result is None:
        # Return partial success - text extracted but analysis failed
        return JsonResponse(
            {
                "success": True,
                "page_count": pdf_result.page_count,
                "text_preview": pdf_result.text_preview,
                "extracted_data": None,
                "extraction_error": "Failed to analyze document.",
            }
        )

    return JsonResponse(
        {
            "success": True,
            "page_count": pdf_result.page_count,
            "text_preview": pdf_result.text_preview,
            "extracted_data": result,
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

    agent = agent_registry["ChatSummarizationAgent"]()

    if not agent.ping():
        return JsonResponse(
            {"error": "Summarize agent is not available"}, status=500
        )

    summary = agent(messages)

    if summary is None:
        return JsonResponse(
            {"error": "Failed to generate summary"}, status=500
        )

    return JsonResponse({"summary": summary})
