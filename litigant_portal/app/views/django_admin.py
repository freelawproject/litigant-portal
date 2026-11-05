import unicodedata

from allauth.core.internal import ratelimit
from django.conf import settings
from django.contrib import admin
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache

RATE_LIMITS = {"admin_login": "10/m/ip,5/5m/key"}


def _login_account(request):
    username = request.POST.get("username", "").strip()
    return unicodedata.normalize("NFKC", username).lower()


def _consume(request, **kwargs):
    return ratelimit.consume(
        request,
        app="admin",
        action="admin_login",
        config=RATE_LIMITS,
        key=_login_account(request),
        **kwargs,
    )


def _enabled():
    return getattr(settings, "RATELIMIT_ENABLE", True)


@never_cache
def login(request, extra_context=None):
    usage = None
    if request.method == "POST" and _enabled():
        # Take the slot before authenticating so concurrent requests cannot
        # all pass the same check.
        usage = _consume(request)
        if usage is None:
            context = {
                **admin.site.each_context(request),
                "title": _("Too many login attempts"),
            }
            return render(
                request, "admin/login_limited.html", context, status=429
            )
    response = admin.site.login(request, extra_context)
    # Like allauth, only failed logins count: a success redirects.
    if usage is not None and response.status_code == 302:
        usage.rollback()
    return response
