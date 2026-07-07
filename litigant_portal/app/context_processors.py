from django.conf import settings
from django.contrib.messages import get_messages

from litigant_portal.app import court_context as court_ctx
from litigant_portal.prompts import get_court_name


def app_meta(request):
    """App-level metadata available in every template."""
    return {
        "deployment_env": settings.DEPLOYMENT_ENV,
        "app_build_time": settings.APP_BUILD_TIME,
    }


def court_context(request):
    """Active court + demo-switcher data for every template.

    ``court_switcher_enabled`` gates the header switcher (dev/QA only);
    ``active_court`` / ``active_court_name`` reflect the session choice so
    court branding is consistent app-wide.
    """
    active = court_ctx.get_active_court(request)
    return {
        "court_switcher_enabled": court_ctx.switcher_enabled(),
        "available_courts": court_ctx.available_courts(),
        "active_court": active,
        "active_court_name": get_court_name(active),
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
