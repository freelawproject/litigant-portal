"""Django system check for the staff two-factor rule.

The rule can be switched off by env. W001 says so at deploy time, so an
instance does not run without it silently. W002 warns when the secrets
are encrypted with SECRET_KEY, so changing it would lock out all staff.
"""

from django.conf import settings
from django.core.checks import Tags, Warning, register


@register(Tags.security)
def check_staff_two_factor(app_configs, **kwargs):
    if settings.STAFF_TWO_FACTOR_REQUIRED or settings.DEBUG:
        return []
    return [
        Warning(
            "STAFF_TWO_FACTOR_REQUIRED is off, so staff accounts can sign "
            "in with a password only.",
            hint="Remove STAFF_TWO_FACTOR_REQUIRED=false to turn the rule "
            "back on.",
            id="two_factor.W001",
        )
    ]


@register(Tags.security)
def check_two_factor_key(app_configs, **kwargs):
    if settings.DEBUG or settings.TWO_FACTOR_KEY != settings.SECRET_KEY:
        return []
    return [
        Warning(
            "TWO_FACTOR_KEY is not set, so two-factor secrets are encrypted "
            "with SECRET_KEY. Changing SECRET_KEY then breaks every staff "
            "sign-in code.",
            hint="Set TWO_FACTOR_KEY to a new key and put the current "
            "SECRET_KEY in TWO_FACTOR_KEY_FALLBACKS.",
            id="two_factor.W002",
        )
    ]
