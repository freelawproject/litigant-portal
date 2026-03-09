from django.contrib.messages import get_messages


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
