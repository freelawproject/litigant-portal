from functools import wraps

from django.http import JsonResponse
from django.utils.translation import gettext as _

from litigant_portal.app.selectors.topic_flow import (
    variable_answer_groups,
    variable_answer_map,
)
from litigant_portal.app.topic_flow.renderer import question_ids


def _has_identity(request) -> bool:
    """Whether this visitor already has an identity worth reading.

    ``request.identity`` resolves lazily by minting a session and a
    ``UserIdentity`` row, so an unguarded read banks one per anonymous hit,
    crawlers included. Every read-only surface checks this first.
    """
    return bool(request.user.is_authenticated or request.session.session_key)


def topic_flow_answers(request, corpus) -> dict:
    """``{question_id: value}`` for this visitor, for the page and downloads.

    Reads through the glossary, so a fact the assistant stored shows up
    here too. Empty for a visitor with no identity yet.
    """
    if not _has_identity(request):
        return {}
    return variable_answer_map(
        identity=request.identity, names=question_ids(corpus)
    )


def briefcase_answers(request) -> list[dict]:
    """The visitor's stored facts, grouped for the briefcase panel.

    Empty for a visitor with no identity yet, which renders as the panel's
    empty state rather than an absent context key.
    """
    if not _has_identity(request):
        return []
    return variable_answer_groups(identity=request.identity)


def _perm_required(codename: str):
    """Build a JSON guard requiring ``codename``."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.has_perm(codename):
                return JsonResponse({"error": _("Forbidden")}, status=403)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


manage_site_required = _perm_required("app.manage_site")
"""JSON guard: requires ``app.manage_site`` (held by the Admins and
Developers groups and, implicitly, superusers)."""

manage_developers_required = _perm_required("app.manage_developers")
"""JSON guard: requires ``app.manage_developers`` (held by the Developers
group and, implicitly, superusers)."""
