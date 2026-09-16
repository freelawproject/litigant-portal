"""Django system check for the docassemble handoff settings.

The prefill fails safe at request time (the litigant gets the plain,
unprefilled interview), so a key without the API root beside it only shows up
as a warning log per handoff. This is the loud counterpart: the half-configured
state surfaces once, at deploy time (#879).
"""

from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.compatibility)
def check_docassemble_settings(app_configs, **kwargs):
    if settings.DOCASSEMBLE_API_KEY and not settings.DOCASSEMBLE_BASE_URL:
        return [
            Warning(
                "DOCASSEMBLE_API_KEY is set but DOCASSEMBLE_BASE_URL is "
                "not, so every prefill attempt fails and falls back to the "
                "plain, unprefilled interview.",
                hint="Set DOCASSEMBLE_BASE_URL to the API root the key "
                "belongs to, or unset the key.",
                id="docassemble.W001",
            )
        ]
    return []
