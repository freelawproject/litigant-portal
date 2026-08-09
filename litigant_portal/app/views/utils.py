from functools import wraps

from django.http import JsonResponse
from django.utils.translation import gettext as _


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
