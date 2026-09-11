from functools import wraps

from django.http import JsonResponse
from django.utils.translation import gettext as _

from litigant_portal.app.selectors.topic_flow import variable_answer_map
from litigant_portal.app.topic_flow.renderer import question_ids


def topic_flow_answers(request, corpus) -> dict:
    """``{question_id: value}`` for this visitor, for the page and downloads.

    Reads through the glossary, so a fact the assistant stored shows up
    here too.
    """
    return _answer_map(request, question_ids(corpus))


def topic_flow_reviewed_answers(request, names: list[str]) -> dict:
    """``{question_id: value}`` for confirmed answers only, for the prefill."""
    return _answer_map(request, names, reviewed_only=True)


def _answer_map(request, names, *, reviewed_only=False) -> dict:
    # Returns empty for a visitor with no session yet rather than touching
    # ``request.identity``, which would mint a session and an identity row
    # for every crawler hitting a flow page.
    if not request.user.is_authenticated and not request.session.session_key:
        return {}
    return variable_answer_map(
        identity=request.identity, names=names, reviewed_only=reviewed_only
    )


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
