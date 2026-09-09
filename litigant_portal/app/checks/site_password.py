"""Django system check for the temporary site-wide password gate.

``SitePasswordMiddleware`` disables itself when ``SITE_PASSWORD`` is empty,
which is the right default for local development and a silent failure anywhere
else: a dropped secret or a typo takes the wall down and serves a pre-launch
portal to the public, with nothing louder than a compose warning at boot.

This check turns that into a startup failure. Taking the wall down on purpose
means silencing the check by id, which is a reviewable config change with a
name attached rather than a value quietly going missing.
"""

from django.conf import settings
from django.core.checks import Error, Tags, register

SITE_PASSWORD_CHECK_ID = "litigant_portal.E001"

# Anything that isn't local development counts as deployed. settings.py keeps
# an unrecognized DEPLOYMENT_ENV as-is and only warns, so testing for "not dev"
# fails closed where testing for "qa or prod" would wave a typo through.
_LOCAL_ENV = "dev"


@register(Tags.security, deploy=False)
def check_site_password_set_when_deployed(app_configs, **kwargs):
    """Error when a deployed environment has no usable site password."""
    if getattr(settings, "DEPLOYMENT_ENV", _LOCAL_ENV) == _LOCAL_ENV:
        return []

    password = getattr(settings, "SITE_PASSWORD", "") or ""
    if password.strip():
        return []

    return [
        Error(
            "SITE_PASSWORD is blank, so the site-wide password gate is off "
            "and every page is public.",
            hint=(
                "Set SITE_PASSWORD in this environment. If the portal is "
                "meant to be public, take the gate down deliberately by "
                f"adding '{SITE_PASSWORD_CHECK_ID}' to SILENCED_SYSTEM_CHECKS."
            ),
            id=SITE_PASSWORD_CHECK_ID,
        )
    ]
