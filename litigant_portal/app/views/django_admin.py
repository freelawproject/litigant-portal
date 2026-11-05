import unicodedata

from django.contrib import admin
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django_ratelimit.core import get_usage


def _login_account(group, request):
    username = request.POST.get("username", "").strip()
    return unicodedata.normalize("NFKC", username).lower()


_LIMITS = (
    {"group": "admin_login_ip", "key": "ip", "rate": "10/m"},
    {"group": "admin_login_account", "key": _login_account, "rate": "5/5m"},
)


def _limited(request, increment):
    """Check both limits, counting this request against them only when
    ``increment`` is set."""
    usages = [
        get_usage(request, method="POST", increment=increment, **limit)
        for limit in _LIMITS
    ]
    return any(u is not None and u["count"] >= u["limit"] for u in usages)


@never_cache
def login(request, extra_context=None):
    if _limited(request, increment=False):
        context = {
            **admin.site.each_context(request),
            "title": _("Too many login attempts"),
        }
        return render(request, "admin/login_limited.html", context, status=429)
    response = admin.site.login(request, extra_context)
    # Like allauth, only failed logins count: a success redirects.
    if request.method == "POST" and response.status_code == 200:
        _limited(request, increment=True)
    return response
