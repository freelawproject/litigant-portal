from django.conf import settings
from django.contrib.messages import get_messages
from django.urls import reverse

from litigant_portal.app.features import features
from litigant_portal.app.selectors.site import site_get
from litigant_portal.app.selectors.topic_flow import (
    topic_flow_list,
    topic_flow_url_kwargs,
)
from litigant_portal.app.views.utils import admin_tabs


def _tester_flow_links(court: str | None) -> list[dict]:
    """Links to the instance's flows for the tester menu: one court's when
    the instance serves one, every court's otherwise."""
    links = []
    for flow in topic_flow_list():
        page = topic_flow_url_kwargs(flow)
        if page and court in (None, page["court"]):
            links.append(
                {
                    "url": reverse("pages:topic_flow", kwargs=page),
                    "title": flow.name,
                }
            )
    return links


def app_meta(request):
    """App-level metadata available in every template."""
    tools = features()
    return {
        "features": tools,
        # Drives the Admin menu link and the dashboard's tabs. Requests
        # built outside the middleware stack carry no user.
        "admin_tabs": (
            admin_tabs(request.user) if hasattr(request, "user") else []
        ),
        "tester_flow_links": (
            _tester_flow_links(settings.CORPUS_COURT)
            if tools.flow_links
            else []
        ),
        "app_build_time": settings.APP_BUILD_TIME,
        "app_git_sha": settings.GIT_SHA,
        "app_git_branch": settings.GIT_BRANCH,
    }


def court_branding(request):
    """The court's name and art for the site header (#979).

    The court's branding name, when it has one, stands in for its court
    name. Blank values mean an instance with no court, where the header
    shows the Free Law Project logo. A view that passes its own values (the style
    guide's samples) overrides these.
    """
    site = site_get()
    return {
        "court_name": site.branding_name or site.court_name,
        "court_logo": site.logo.url if site.logo else "",
        "court_name_image": site.name_image.url if site.name_image else "",
    }


def toast_messages(request):
    """
    Provide messages with variant mapped for alert component.

    Django's 'error' tag maps to 'danger' variant.
    """
    tag_to_variant = {
        "error": "danger",
    }

    messages = []
    for message in get_messages(request):
        messages.append(
            {
                "text": str(message),
                "variant": tag_to_variant.get(message.tags, message.tags)
                or "info",
            }
        )

    return {"toast_messages": messages}
