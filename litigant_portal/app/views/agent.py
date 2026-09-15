"""
Development UI and persisted Direct conversations for the new agent.
"""

import logging
from hashlib import sha256

from asgiref.sync import async_to_sync
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from litigant_portal.agent import PortalAgent
from litigant_portal.app.selectors.agent import Court, agent_scope_choices
from litigant_portal.app.selectors.site import site_get_model
from litigant_portal.app.views.utils import manage_developers_required
from lp_agent import AgentAccessError, AgentValidationError, RunLimits
from lp_agent.adapters.bedrock import MODEL_CHOICES
from lp_agent.adapters.conversations import conversation_snapshot
from lp_agent.errors import AgentStorageError
from lp_agent.types import AccessContext

logger = logging.getLogger(__name__)
SERVICE_UNAVAILABLE = "Agent service is unavailable. Please try again later."
UNSUPPORTED_TOOL_MODEL = "bedrock_mantle/zai.glm-4.7-flash"


@login_required
@permission_required("app.manage_developers", raise_exception=True)
@never_cache
@require_GET
def development_page(request: HttpRequest) -> HttpResponse:
    """
    Render configuration controls without constructing or running an agent.
    """
    if not settings.LP_AGENT_DEV_ENABLED:
        raise Http404
    selected_model = site_get_model(role="assistant")
    if (
        selected_model not in dict(MODEL_CHOICES)
        or selected_model == UNSUPPORTED_TOOL_MODEL
    ):
        selected_model = None
    service_error = ""
    try:
        courts = agent_scope_choices()
    except (AgentStorageError, AgentValidationError):
        courts = ()
        service_error = SERVICE_UNAVAILABLE
    return render(
        request,
        "pages/agent/development.html",
        {
            "courts": courts,
            "service_error": service_error,
            "unsupported_tool_model": UNSUPPORTED_TOOL_MODEL,
            "model_choices": MODEL_CHOICES,
            "selected_model": selected_model,
            "limits": RunLimits(),
            "agent_script_version": sha256(
                (
                    settings.BASE_DIR / "app/static/js/agent_development.js"
                ).read_bytes()
            ).hexdigest()[:12],
        },
        status=503 if service_error else 200,
    )


class AgentMessageForm(forms.Form):
    """
    Validate browser-owned inputs before accepting a streaming response.
    """

    message = forms.CharField(strip=False)
    court = forms.ChoiceField(
        required=False,
        error_messages={"invalid_choice": "Select an available court."},
    )
    topic = forms.ChoiceField(
        required=False,
        error_messages={
            "invalid_choice": "Select a topic available for this court."
        },
    )
    model = forms.ChoiceField(
        choices=MODEL_CHOICES,
        error_messages={
            "invalid_choice": "Select an available Bedrock model."
        },
    )
    conversation_id = forms.UUIDField(required=False)
    judge = forms.ChoiceField(
        required=False, choices=(("", "Same as assistant"), *MODEL_CHOICES)
    )
    max_active_seconds = forms.FloatField(min_value=0.1)

    def __init__(self, *args, courts: tuple[Court, ...], **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["court"].choices = [
            (court.choice_id, court.label) for court in courts
        ]
        self.fields["topic"].choices = [
            (topic.choice_id, topic.label)
            for court in courts
            if not self["court"].value()
            or court.choice_id == self["court"].value()
            for topic in court.topics
        ]

    def clean(self):
        data = super().clean()
        if not data.get("message", "").strip():
            self.add_error("message", "Enter a message.")
        if data.get("model") == UNSUPPORTED_TOOL_MODEL:
            self.add_error(
                "model",
                "This model does not support preparation tools. Select a native Bedrock model.",
            )
        return data


@login_required
@manage_developers_required
@require_POST
def development_stream(request: HttpRequest) -> HttpResponse:
    """
    Stream one conversation turn using the request's verified identity.
    """
    if not settings.LP_AGENT_DEV_ENABLED:
        raise Http404
    try:
        courts = agent_scope_choices()
    except (AgentStorageError, AgentValidationError):
        return JsonResponse({"error": SERVICE_UNAVAILABLE}, status=503)
    form = AgentMessageForm(request.POST, courts=courts)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)
    if not settings.BEDROCK_API_KEY.strip():
        logger.warning(
            "Agent configuration unavailable: Bedrock API key is missing."
        )
        return JsonResponse(
            {"error": "Agent service is unavailable. Please try again later."},
            status=503,
        )
    data = form.cleaned_data
    try:
        agent = PortalAgent(
            identity=request.identity,
            court=data["court"] or None,
            topic=data["topic"] or None,
            judge=data["judge"] or None,
            model=data["model"],
            runtime="Direct",
            limits=RunLimits(max_active_seconds=data["max_active_seconds"]),
        )
    except (AgentValidationError, ValidationError):
        logger.warning("Agent initialization failed: invalid configuration.")
        return JsonResponse(
            {"error": "Invalid agent configuration."}, status=400
        )
    response = StreamingHttpResponse(
        agent.stream(
            message=data["message"],
            conversation_id=str(data["conversation_id"])
            if data["conversation_id"]
            else None,
        ),
        content_type="application/x-ndjson",
    )
    response["Cache-Control"] = "no-store"
    response["X-Accel-Buffering"] = "no"
    return response


@login_required
@manage_developers_required
@require_GET
def development_conversation(
    request: HttpRequest, conversation_id
) -> HttpResponse:
    """
    Restore the current identity's conversation without exposing internal model data.
    """
    if not settings.LP_AGENT_DEV_ENABLED:
        raise Http404
    try:
        result = async_to_sync(conversation_snapshot)(
            AccessContext(identity_id=str(request.identity.pk)),
            str(conversation_id),
        )
    except AgentAccessError:
        return JsonResponse(
            {"error": "Conversation is unavailable."}, status=404
        )
    except (AgentStorageError, AgentValidationError):
        return JsonResponse(
            {"error": "Agent service is unavailable. Please try again later."},
            status=503,
        )
    response = JsonResponse(result)
    response["Cache-Control"] = "no-store"
    return response
