
# =============================================================================
# Case info endpoints
# =============================================================================


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def case_get(request: HttpRequest) -> JsonResponse:
    """Return case info + timeline for the current user/session."""
    case = CaseInfo.objects.filter(
        status="active", identity=request.identity
    ).first()

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

    case, created = CaseInfo.objects.update_or_create(
        status="active",
        defaults={"data": data},
        identity=request.identity,
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

    case, _ = CaseInfo.objects.get_or_create(identity=request.identity)

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
    case = CaseInfo.objects.filter(identity=request.identity).first()
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
    archived = CaseInfo.objects.filter(
        status="active", identity=request.identity
    ).update(status="archived")
    request.session.pop("chat_session_id", None)

    return JsonResponse({"archived": archived > 0})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def case_resolve(request: HttpRequest) -> JsonResponse:
    """Mark the active case as resolved and create a resolution timeline event."""
    case = CaseInfo.objects.filter(
        status="active", identity=request.identity
    ).first()

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
    item = ActionItemModel.objects.filter(
        id=item_id,
        case__status="active",
        case__identity=request.identity,
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
    deadline = Deadline.objects.filter(
        id=deadline_id,
        case__status="active",
        case__identity=request.identity,
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
