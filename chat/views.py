import json

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from litigant_portal.agents import agent_registry

from .models import ActionItemModel, CaseInfo, Deadline, TimelineEvent
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
    topic = request.POST.get("topic", "").strip() or None
    court = request.POST.get("court", "").strip() or None

    if not message:
        return JsonResponse({"error": _("Message is required")}, status=400)

    if len(message) > 2000:
        return JsonResponse(
            {"error": _("Message is too long (max 2000 characters)")},
            status=400,
        )

    try:
        chat = ChatService(
            request,
            session_id=session_id,
            agent_name=agent_name,
            topic=topic,
            court=court,
        )
        request.session["chat_session_id"] = str(chat.agent.session.id)
        return chat.stream(message)
    except PermissionError:
        return JsonResponse({"error": _("Unauthorized")}, status=403)
    except ValueError:
        return JsonResponse(
            {"error": _("Error loading chat session")}, status=404
        )
    except KeyError:
        return JsonResponse({"error": _("Agent not found")}, status=404)


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
        return JsonResponse({"error": _("No file uploaded")}, status=400)

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
                "extraction_error": _("Failed to analyze document."),
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
        return JsonResponse({"error": _("Messages are required")}, status=400)

    try:
        messages = json.loads(messages_raw)
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": _("Invalid messages format")}, status=400
        )

    if not isinstance(messages, list) or len(messages) < 2:
        return JsonResponse(
            {"error": _("At least 2 messages required for summary")},
            status=400,
        )

    agent = agent_registry["ChatSummarizationAgent"]()

    if not agent.ping():
        return JsonResponse(
            {"error": _("Summarize agent is not available")}, status=500
        )

    summary = agent(messages)

    if summary is None:
        return JsonResponse(
            {"error": _("Failed to generate summary")}, status=500
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
    case = CaseInfo.objects.filter(status="active", **ownership).first()

    if not case:
        return JsonResponse({"case_info": None, "timeline": []})

    # Assemble case_info: JSON fields + model-backed fields
    case_info = dict(case.data)
    case_info["status"] = case.status
    case_info["key_dates"] = [d.to_dict() for d in case.deadlines.all()]
    case_info["action_items"] = [a.to_dict() for a in case.action_items.all()]

    timeline = list(
        case.timeline_events.values(
            "id", "event_type", "title", "content", "metadata", "created_at"
        )
    )
    # Serialize UUIDs and datetimes
    for event in timeline:
        event["id"] = str(event["id"])
        event["created_at"] = event["created_at"].isoformat()

    return JsonResponse({"case_info": case_info, "timeline": timeline})


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

    # Strip model-backed fields before saving to JSON
    key_dates = data.pop("key_dates", [])
    action_items = data.pop("action_items", [])

    ownership = _ownership_filter(request)
    case, created = CaseInfo.objects.update_or_create(
        status="active",
        defaults={"data": data},
        **ownership,
    )

    # Upsert key_dates into Deadline model
    for date_dict in key_dates:
        if not case.deadlines.filter(
            label=date_dict.get("label", ""),
            date=date_dict.get("date", ""),
        ).exists():
            case.deadlines.create(
                label=date_dict.get("label", ""),
                date=date_dict.get("date", ""),
                is_deadline=date_dict.get("is_deadline", False),
            )

    # Upsert action_items into ActionItemModel
    for item_dict in action_items:
        title = item_dict.get("title", "")
        if title and not case.action_items.filter(title=title).exists():
            case.action_items.create(
                title=title,
                description=item_dict.get("description", ""),
                priority=item_dict.get("priority", "normal"),
                deadline=item_dict.get("deadline") or "",
                href=item_dict.get("href") or "",
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

    valid_types = {"upload", "summary", "change", "resolution"}
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


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def action_plan(request: HttpRequest):
    """Render a print-friendly action plan document from CaseInfo data."""
    ownership = _ownership_filter(request)
    case = CaseInfo.objects.filter(**ownership).first()
    data = case.data if case else {}

    key_dates = [d.to_dict() for d in case.deadlines.all()] if case else []
    action_items = (
        [a.to_dict() for a in case.action_items.all()] if case else []
    )

    return render(
        request,
        "pages/action_plan.html",
        {
            "case_type": data.get("case_type", ""),
            "summary": data.get("summary", ""),
            "court_info": data.get("court_info", {}),
            "parties": data.get("parties", {}),
            "key_dates": key_dates,
            "action_items": action_items,
            "spotted_issues": data.get("spotted_issues", []),
            "resources": data.get("resources", []),
            "has_data": bool(data) or bool(key_dates) or bool(action_items),
        },
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def case_clear(request: HttpRequest) -> JsonResponse:
    """Archive active case info. Clear chat session from Django session."""
    ownership = _ownership_filter(request)
    archived = CaseInfo.objects.filter(status="active", **ownership).update(
        status="archived"
    )
    request.session.pop("chat_session_id", None)

    return JsonResponse({"archived": archived > 0})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def case_resolve(request: HttpRequest) -> JsonResponse:
    """Mark the active case as resolved and create a resolution timeline event."""
    ownership = _ownership_filter(request)
    case = CaseInfo.objects.filter(status="active", **ownership).first()

    if not case:
        return JsonResponse({"resolved": False})

    case.status = "resolved"
    case.save(update_fields=["status"])

    TimelineEvent.objects.create(
        case=case,
        event_type="resolution",
        title="Case marked as resolved",
    )

    return JsonResponse({"resolved": True})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def action_item_toggle(request: HttpRequest, item_id: str) -> JsonResponse:
    """Toggle an action item's completed state."""
    ownership = _ownership_filter(request)
    item = ActionItemModel.objects.filter(
        id=item_id,
        case__status="active",
        **{"case__" + k: v for k, v in ownership.items()},
    ).first()

    if not item:
        return JsonResponse({"error": "Not found"}, status=404)

    item.completed = not item.completed
    item.save(update_fields=["completed"])

    return JsonResponse({"id": str(item.id), "completed": item.completed})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def deadline_reminder_toggle(
    request: HttpRequest, deadline_id: str
) -> JsonResponse:
    """Toggle a deadline's reminder_requested state."""
    ownership = _ownership_filter(request)
    deadline = Deadline.objects.filter(
        id=deadline_id,
        case__status="active",
        **{"case__" + k: v for k, v in ownership.items()},
    ).first()

    if not deadline:
        return JsonResponse({"error": "Not found"}, status=404)

    deadline.reminder_requested = not deadline.reminder_requested
    deadline.save(update_fields=["reminder_requested"])

    return JsonResponse(
        {
            "id": str(deadline.id),
            "reminder_requested": deadline.reminder_requested,
        }
    )
