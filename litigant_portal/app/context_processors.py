from django.conf import settings
from django.contrib.messages import get_messages
from django.utils.functional import SimpleLazyObject

from litigant_portal.app.services.admin import (
    user_can_access_admin,
    user_is_developer,
)


def app_meta(request):
    """App-level metadata available in every template."""
    return {
        "deployment_env": settings.DEPLOYMENT_ENV,
        "app_build_time": settings.APP_BUILD_TIME,
    }


def admin_access(request):
    """Whether the current user may see the admin panel."""
    return {
        "can_access_admin": SimpleLazyObject(
            lambda: user_can_access_admin(user=request.user)
        )
    }


def developer_access(request):
    """Whether the current user is a developer."""
    return {
        "is_developer": SimpleLazyObject(
            lambda: user_is_developer(user=request.user)
        )
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
