"""
Development UI and independent Direct runs for the new agent.
"""

import os

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
from litigant_portal.app.selectors.agent import agent_scope_choices
from litigant_portal.app.selectors.site import site_get_model
from lp_agent import AgentValidationError, RunLimits
from lp_agent.adapters.bedrock import MODEL_CHOICES
from lp_agent.adapters.catalog import Court
from lp_agent.types import Choice


@login_required
@permission_required("app.manage_developers", raise_exception=True)
@require_GET
def development_page(request: HttpRequest) -> HttpResponse:
    """
    Render configuration controls without constructing or running an agent.
    """
    if not settings.LP_AGENT_DEV_ENABLED:
        raise Http404
    courts, topics = agent_scope_choices()
    return render(
        request,
        "pages/agent/development.html",
        {
            "courts": courts,
            "topics": topics,
            "model_choices": MODEL_CHOICES,
            "selected_model": site_get_model(role="assistant"),
            "limits": RunLimits(),
        },
    )


class AgentMessageForm(forms.Form):
    """
    Validate browser-owned inputs before accepting a streaming response.
    """

    message = forms.CharField(strip=False)
    court = forms.CharField()
    topic = forms.CharField()
    model = forms.ChoiceField(choices=MODEL_CHOICES)
    max_active_seconds = forms.FloatField(min_value=0.1)
    interrupt_behavior = forms.ChoiceField(
        choices=[("reject", "Reject while busy")], required=False
    )

    def __init__(self, *args, topics, **kwargs):
        super().__init__(*args, **kwargs)
        self.topics = topics

    def clean(self):
        data = super().clean()
        if not data.get("message", "").strip():
            self.add_error("message", "Enter a message.")
        if (
            data.get("court")
            and data.get("topic")
            and not any(
                item["court"] == data["court"]
                and item["slug"] == data["topic"]
                for item in self.topics
            )
        ):
            self.add_error("topic", "Select a topic available for this court.")
        return data


@login_required
@permission_required("app.manage_developers", raise_exception=True)
@require_POST
def development_stream(request: HttpRequest) -> HttpResponse:
    """
    Stream one fully scoped response using the request's verified identity.
    """
    if not settings.LP_AGENT_DEV_ENABLED:
        raise Http404
    courts, topics = agent_scope_choices()
    form = AgentMessageForm(request.POST, topics=topics)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)
    data = form.cleaned_data
    try:
        agent = PortalAgent(
            identity=request.identity,
            court=data["court"],
            topic=data["topic"],
            model=data["model"],
            api_key=os.environ.get("AWS_BEARER_TOKEN_BEDROCK", ""),
            catalog=tuple(
                Court(
                    choice_id=court["slug"],
                    label=court["name"],
                    topics=tuple(
                        Choice(choice_id=topic["slug"], label=topic["title"])
                        for topic in topics
                        if topic["court"] == court["slug"]
                    ),
                )
                for court in courts
            ),
            runtime="Direct",
            limits=RunLimits(max_active_seconds=data["max_active_seconds"]),
        )
    except (AgentValidationError, ValidationError):
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
