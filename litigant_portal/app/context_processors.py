from django.conf import settings
from django.contrib.messages import get_messages

from litigant_portal.app.selectors.site import site_get


def app_meta(request):
    """App-level metadata available in every template."""
    return {
        "deployment_env": settings.DEPLOYMENT_ENV,
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
