"""
Development UI for the new agent. Execution is connected in a later step.
"""

from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from litigant_portal.agent import RunLimits
from litigant_portal.app.models.choices import BedrockModel
from litigant_portal.app.selectors.agent import agent_scope_choices
from litigant_portal.app.selectors.site import site_get_model


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
            "model_choices": BedrockModel.choices,
            "selected_model": site_get_model(role="assistant"),
            "limits": RunLimits(),
        },
    )
