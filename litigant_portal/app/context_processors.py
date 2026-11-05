from django.conf import settings
from django.contrib.messages import get_messages
from django.templatetags.static import static
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from litigant_portal.app.features import features
from litigant_portal.app.selectors.corpus import corpus_load_courts
from litigant_portal.app.selectors.site import site_get
from litigant_portal.app.selectors.topic_flow import (
    topic_court_find,
    topic_flow_list,
    topic_flow_url_kwargs,
)
from litigant_portal.app.views.utils import (
    ALL_COURTS,
    BRANDING_FIELDS,
    admin_tabs,
    password_rule,
)


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


# All courts, branded as a court of its own wherever the court switcher is on
# (#886): the FLP logo as its seal, under this name.
OMNI_COURT_NAME = _("Omni Court")
OMNI_COURT_LOGO = "images/logo.svg"


def _tester_court_choices() -> list[dict]:
    """The court switcher's choices (#886): all courts, then each corpus
    court, with the court the site is on now selected."""
    courts = corpus_load_courts()
    current = topic_court_find() or ALL_COURTS
    choices = [
        {
            "value": ALL_COURTS,
            "label": OMNI_COURT_NAME,
            "logo_url": static(OMNI_COURT_LOGO),
            "name_image_url": "",
        }
    ]
    for slug, court in courts.items():
        choice = {
            "value": slug,
            # The name the header would show once switched.
            "label": court.branding.name or court.court_name,
        }
        for field in BRANDING_FIELDS:
            choice[f"{field}_url"] = (
                reverse(
                    "pages:court_branding",
                    kwargs={"court": slug, "field": field},
                )
                if getattr(court.branding, field)
                else ""
            )
        choices.append(choice)
    for choice in choices:
        choice["selected"] = choice["value"] == current
    return choices


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
        "tester_court_choices": (
            _tester_court_choices() if tools.court_switcher else []
        ),
        # Every new-password field states the same rules (#1135).
        "password_rules": password_rule(),
        "app_build_time": settings.APP_BUILD_TIME,
        "app_git_sha": settings.GIT_SHA,
        "app_git_branch": settings.GIT_BRANCH,
    }


def court_branding(request):
    """The court's name and art for the site header (#979).

    The court's branding name, when it has one, stands in for its court
    name. Blank values mean an instance with no court, where the header
    shows the Free Law Project logo, except where the court switcher is on:
    there all courts is Omni Court, with the FLP logo as its seal (#886). A
    view that passes its own values (the style guide's samples) overrides
    these.
    """
    site = site_get()
    if not site.court_name and features().court_switcher:
        return {
            "court_name": str(OMNI_COURT_NAME),
            "court_logo": static(OMNI_COURT_LOGO),
            "court_name_image": "",
        }
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
