"""Which tester tools each deployment shows (#1037).

The layers are additive, from two settings:

- prod, or ``DEPLOYMENT_ENV`` unset or unknown: no tools (#1008).
- ``PILOT=true``: adds the pilot tools a court tests with.
- dev and qa: the pilot tools plus FLP's own (court switcher, citation
  chips), so there's no reason to set ``PILOT`` there; the pilot tools can
  be tested directly.

Templates and views check a feature here, never the environment, so a
tool's layer changes in one place and the server and the page can't
disagree. The build stamp's label reports the settings themselves, so an
instance shows what it's configured as.
"""

import logging
from dataclasses import dataclass

from django.conf import settings

logger = logging.getLogger(__name__)

DEPLOYMENT_ENVS = frozenset({"dev", "qa", "prod"})
FLP_ENVS = frozenset({"dev", "qa"})

GITHUB_FEEDBACK_URL = (
    "https://github.com/freelawproject/litigant-portal/issues/new"
)


@dataclass(frozen=True)
class Features:
    # The settings as the build stamp shows them ("dev", "qa", "pilot",
    # "qa · pilot"); blank on plain prod, which has no stamp.
    stamp_label: str
    # Pilot tools.
    build_stamp: bool
    start_over: bool
    court_user_admin: bool
    flow_links: bool
    style_guide: bool
    # Blank when there's no feedback link.
    feedback_url: str
    # FLP tools, dev and qa only.
    court_switcher: bool
    citation_chips: bool


def parse_deployment_env(raw: str | None) -> str:
    """The deployment env, or prod when it's unset or not a known value."""
    if raw in DEPLOYMENT_ENVS:
        return raw
    if raw:
        logger.warning(
            "DEPLOYMENT_ENV=%r is not one of %s; running as prod.",
            raw,
            sorted(DEPLOYMENT_ENVS),
        )
    return "prod"


def parse_pilot(raw: str | None) -> bool:
    """Only the exact value ``true`` turns a pilot on."""
    return raw == "true"


def _stamp_label(env: str, pilot: bool) -> str:
    parts = [env] if env in FLP_ENVS else []
    if pilot:
        parts.append("pilot")
    return " · ".join(parts)


def _feedback_url(flp: bool, pilot: bool, feedback_email: str) -> str:
    if flp:
        return GITHUB_FEEDBACK_URL
    if pilot and feedback_email:
        return f"mailto:{feedback_email}"
    return ""


def features_for(env: str, pilot: bool, *, feedback_email: str) -> Features:
    flp = env in FLP_ENVS
    pilot_tools = flp or pilot
    return Features(
        stamp_label=_stamp_label(env, pilot),
        build_stamp=pilot_tools,
        start_over=pilot_tools,
        court_user_admin=pilot_tools,
        flow_links=pilot_tools,
        style_guide=pilot_tools,
        feedback_url=_feedback_url(flp, pilot, feedback_email),
        court_switcher=flp,
        citation_chips=flp,
    )


def features() -> Features:
    """The features for the current settings, read on each call so
    ``override_settings`` and per-request checks see the same values."""
    return features_for(
        settings.DEPLOYMENT_ENV,
        settings.PILOT,
        feedback_email=settings.FEEDBACK_EMAIL,
    )
