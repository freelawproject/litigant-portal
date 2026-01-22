from pathlib import Path

from django.conf import settings
from django.contrib.messages import get_messages


def build_info(request):
    """Provide build timestamp for footer display (DEBUG mode only)."""
    if not settings.DEBUG:
        return {"build_timestamp": None}

    timestamp_file = Path(settings.BASE_DIR) / "BUILD_TIMESTAMP"
    if timestamp_file.exists():
        timestamp = timestamp_file.read_text().strip()
    else:
        timestamp = "dev"
    return {"build_timestamp": timestamp}


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
