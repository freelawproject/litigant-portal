import json

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from .agents import agent_registry
from .models import CaseInfo, TimelineEvent
from .services.chat_service import ChatService
from .services.pdf_service import pdf_service
from .services.search_service import search_service


def _ownership_filter(request: HttpRequest) -> dict:
    """Return query filter for the current user's data.

    Authenticated users match by user FK, anonymous users by session_key.
    Same dual-ownership pattern as ChatSession.
    """
    if request.user.is_authenticated:
        return {"user": request.user}
    if not request.session.session_key:
        request.session.create()
    return {"session_key": request.session.session_key}


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
    session_id = (
        request.POST.get("session_id")
        or request.session.get("chat_session_id")
        or None
    )
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
        request.session["chat_session_id"] = str(chat.agent.session.id)
        return chat.stream(message)
    except PermissionError:
        return JsonResponse({"error": "Unauthorized"}, status=403)
    except ValueError:
        return JsonResponse(
            {"error": "Error loading chat session"}, status=404
        )
    except KeyError:
        return JsonResponse(
            {"error": f"Agent {agent_name} not found"}, status=404
        )


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


# =============================================================================
# Case info endpoints
# =============================================================================


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def case_get(request: HttpRequest) -> JsonResponse:
    """Return case info + timeline for the current user/session."""
    ownership = _ownership_filter(request)
    case = CaseInfo.objects.filter(**ownership).first()

    if not case:
        return JsonResponse({"case_info": None, "timeline": []})

    timeline = list(
        case.timeline_events.values(
            "id", "event_type", "title", "content", "metadata", "created_at"
        )
    )
    # Serialize UUIDs and datetimes
    for event in timeline:
        event["id"] = str(event["id"])
        event["created_at"] = event["created_at"].isoformat()

    return JsonResponse({"case_info": case.data, "timeline": timeline})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def case_save(request: HttpRequest) -> JsonResponse:
    """Create or update case info."""
    raw_data = request.POST.get("data", "")
    if not raw_data:
        return JsonResponse({"error": "data is required"}, status=400)

    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON in data"}, status=400)

    if not isinstance(data, dict):
        return JsonResponse(
            {"error": "data must be a JSON object"}, status=400
        )

    ownership = _ownership_filter(request)
    case, created = CaseInfo.objects.update_or_create(
        defaults={"data": data},
        **ownership,
    )

    return JsonResponse({"id": str(case.id), "created": created})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def case_timeline_add(request: HttpRequest) -> JsonResponse:
    """Add a timeline event. Auto-creates CaseInfo if needed."""
    event_type = request.POST.get("event_type", "")
    title = request.POST.get("title", "")
    content = request.POST.get("content", "")
    raw_metadata = request.POST.get("metadata", "{}")

    valid_types = {"upload", "summary", "change"}
    if event_type not in valid_types:
        return JsonResponse(
            {
                "error": f"event_type must be one of: {', '.join(sorted(valid_types))}"
            },
            status=400,
        )

    try:
        metadata = json.loads(raw_metadata)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON in metadata"}, status=400)

    ownership = _ownership_filter(request)
    case, _ = CaseInfo.objects.get_or_create(**ownership)

    event = TimelineEvent.objects.create(
        case=case,
        event_type=event_type,
        title=title,
        content=content,
        metadata=metadata,
    )

    return JsonResponse({"id": str(event.id)})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def case_clear(request: HttpRequest) -> JsonResponse:
    """Delete case info + cascade timeline. Clear chat session from Django session."""
    ownership = _ownership_filter(request)
    deleted, _ = CaseInfo.objects.filter(**ownership).delete()
    request.session.pop("chat_session_id", None)

    return JsonResponse({"deleted": deleted > 0})
