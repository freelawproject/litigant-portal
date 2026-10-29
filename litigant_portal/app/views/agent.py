"""
Development UI and independent Direct runs for the new agent.
"""

import logging

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
from django.views.decorators.http import require_GET, require_POST
from pydantic import ValidationError

from litigant_portal.agent import PortalAgent
from litigant_portal.app.selectors.agent import Court, agent_scope_choices
from litigant_portal.app.selectors.bedrock import bedrock_model_choices
from litigant_portal.app.selectors.site import site_get
from litigant_portal.app.views.utils import manage_developers_required
from lp_agent import AgentValidationError, RunLimits
from lp_agent.adapters.bedrock_models import (
    BedrockModelUnavailable,
    default_model,
    model_choices,
)

logger = logging.getLogger(__name__)


@login_required
@permission_required("app.manage_developers", raise_exception=True)
@require_GET
def development_page(request: HttpRequest) -> HttpResponse:
    """
    Render configuration controls without constructing or running an agent.
    """
    if not settings.LP_AGENT_DEV_ENABLED:
        raise Http404
    choices = ()
    model_error = ""
    selected_model = site_get().assistant_model
    try:
        choices = bedrock_model_choices()
        if not selected_model:
            selected_model = default_model("assistant", dict(choices))
    except BedrockModelUnavailable as error:
        model_error = str(error)
    if selected_model not in dict(choices):
        selected_model = None
    return render(
        request,
        "pages/agent/development.html",
        {
            "courts": agent_scope_choices(),
            "model_choices": choices,
            "model_error": model_error,
            "selected_model": selected_model,
            "limits": RunLimits(),
        },
    )


class AgentMessageForm(forms.Form):
    """
    Validate browser-owned inputs before accepting a streaming response.
    """

    message = forms.CharField(strip=False)
    court = forms.ChoiceField(
        error_messages={"invalid_choice": "Select an available court."}
    )
    topic = forms.ChoiceField(
        error_messages={
            "invalid_choice": "Select a topic available for this court."
        }
    )
    model = forms.ChoiceField(
        error_messages={
            "invalid_choice": "Select an available Bedrock model."
        },
    )
    max_active_seconds = forms.FloatField(min_value=0.1)

    def __init__(
        self,
        *args,
        courts: tuple[Court, ...],
        model_choices: tuple[tuple[str, str], ...],
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.fields["model"].choices = model_choices
        self.fields["court"].choices = [
            (court.choice_id, court.label) for court in courts
        ]
        self.fields["topic"].choices = [
            (topic.choice_id, topic.label)
            for court in courts
            if court.choice_id == self["court"].value()
            for topic in court.topics
        ]

    def clean(self):
        data = super().clean()
        if not data.get("message", "").strip():
            self.add_error("message", "Enter a message.")
        return data


@login_required
@manage_developers_required
@require_POST
def development_stream(request: HttpRequest) -> HttpResponse:
    """
    Stream one fully scoped response using the request's verified identity.
    """
    if not settings.LP_AGENT_DEV_ENABLED:
        raise Http404
    form = AgentMessageForm(
        request.POST,
        courts=agent_scope_choices(),
        model_choices=model_choices(),
    )
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
    try:
        data = form.cleaned_data
        if data["model"] not in dict(bedrock_model_choices()):
            form.add_error("model", "Select an available Bedrock model.")
            return JsonResponse({"errors": form.errors}, status=400)
        agent = PortalAgent(
            identity=request.identity,
            court=data["court"],
            topic=data["topic"],
            model=data["model"],
            runtime="Direct",
            limits=RunLimits(max_active_seconds=data["max_active_seconds"]),
        )
    except BedrockModelUnavailable:
        logger.warning("Agent model discovery failed.")
        return JsonResponse(
            {"error": "Agent service is unavailable. Please try again later."},
            status=503,
        )
    except (AgentValidationError, ValidationError):
        logger.warning("Agent initialization failed: invalid configuration.")
        return JsonResponse(
            {"error": "Invalid agent configuration."}, status=400
        )
    response = StreamingHttpResponse(
        agent.stream(message=data["message"]),
        content_type="application/x-ndjson",
    )
    response["Cache-Control"] = "no-store"
    response["X-Accel-Buffering"] = "no"
    return response
