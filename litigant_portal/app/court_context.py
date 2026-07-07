"""Active-court context for the demo court switcher (#632).

In dev/QA a hot-switcher lets Jessica and court partners flip the active court
on the fly; the choice is stored in the session so it persists across
navigation. In production the switcher is hidden and the court comes from a
per-court config object instead (future), so the session key is simply never
set and ``get_active_court`` returns "".

All logic lives here so the view, the context processor, and future callers
share one validated path — and so the underscore/hyphen and unknown-slug
edge cases are handled in exactly one place.
"""

from django.conf import settings

from litigant_portal.prompts import is_known_court, iter_courts

SESSION_KEY = "active_court"


def switcher_enabled() -> bool:
    """The demo court switcher is shown only outside production."""
    return settings.DEPLOYMENT_ENV != "prod"


def get_active_court(request) -> str:
    """Return the session's active court slug, or "" if none or invalid.

    Validated against the court registry so a stale or tampered session value
    can't leak an unknown court downstream — callers treat "" as "no court".
    """
    slug = request.session.get(SESSION_KEY, "")
    return slug if is_known_court(slug) else ""


def set_active_court(request, slug: str) -> str:
    """Set (or clear) the active court in the session; return the result.

    A known court slug is stored. Anything else — including "" for the
    generic / no-court option — clears the key. Returns the resulting slug
    ("" when cleared).
    """
    slug = (slug or "").strip().lower()
    if slug and is_known_court(slug):
        request.session[SESSION_KEY] = slug
        return slug
    request.session.pop(SESSION_KEY, None)
    return ""


def available_courts() -> list[dict]:
    """Courts the switcher can pick from — ``[{"slug", "name"}, ...]``."""
    return [
        {"slug": slug, "name": meta.get("name") or slug}
        for slug, meta in iter_courts()
    ]
