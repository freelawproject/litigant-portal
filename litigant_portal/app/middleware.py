import secrets

from django.conf import settings
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.functional import SimpleLazyObject
from django.utils.http import urlencode
from django_ratelimit.core import is_ratelimited

from litigant_portal.app.models import UserIdentity
from litigant_portal.app.services.user import (
    user_identity_anonymous_settle,
    user_identity_ensure,
)
from litigant_portal.app.session import ANONYMOUS_SESSION_KEY


def _gate_exempt_paths() -> tuple[str, ...]:
    """Path prefixes the site gate and the answers check leave alone:
    static files, media and the API."""
    return tuple(
        p for p in (settings.STATIC_URL, settings.MEDIA_URL, "/api/") if p
    )


class SitePasswordMiddleware:
    """Temporary password gate on pages (not /api/), active only when
    SITE_PASSWORD is set — it keeps visitors from mistaking the dev site
    for a live service. To remove: delete this class, its MIDDLEWARE entry,
    the SITE_PASSWORD setting, and templates/site_password.html."""

    SESSION_KEY = "site_password_ok"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        password = settings.SITE_PASSWORD
        if (
            not password
            or request.session.get(self.SESSION_KEY)
            or request.path.startswith(_gate_exempt_paths())
        ):
            return self.get_response(request)
        if request.method == "POST" and "site_password" in request.POST:
            if is_ratelimited(
                request,
                group="site_password",
                key="ip",
                rate="10/m",
                method="POST",
                increment=True,
            ):
                return render(
                    request,
                    "site_password.html",
                    {"limited": True},
                    status=429,
                )
            if secrets.compare_digest(
                request.POST["site_password"].encode(), password.encode()
            ):
                request.session[self.SESSION_KEY] = True
                return redirect(request.get_full_path())
            return render(request, "site_password.html", {"error": True})
        return render(request, "site_password.html")


class AnonymousSessionKeyMiddleware:
    """Carry the anonymous session's key across login, then ask what to
    do with what that session holds.

    While the visitor is anonymous, their session key is copied into the
    session data. Django's ``login()`` rotates the key but keeps the data,
    so the copy survives. Signed in with the copy still there, a GET
    anywhere but the exempt paths redirects to the answers page with the
    current path as ``next``, and keeps doing so until a choice there
    removes the copy. GET only, so a POST from a tab opened before login
    still goes through. With nothing to bring, the copy and the empty
    identity row go at once and the page is never shown.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session = request.session
        if not request.user.is_authenticated:
            if (
                session.session_key
                and session.get(ANONYMOUS_SESSION_KEY) != session.session_key
            ):
                session[ANONYMOUS_SESSION_KEY] = session.session_key
            return self.get_response(request)
        session_key = session.get(ANONYMOUS_SESSION_KEY)
        if (
            session_key
            and request.method == "GET"
            and not _answers_exempt(request)
        ):
            counts = user_identity_anonymous_settle(session_key=session_key)
            if any(counts.values()):
                query = urlencode({"next": request.get_full_path()})
                return redirect(
                    f"{reverse('pages:anonymous_answers')}?{query}"
                )
            del session[ANONYMOUS_SESSION_KEY]
        return self.get_response(request)


def _answers_exempt(request) -> bool:
    """Whether the answers check leaves this request alone: the page
    itself, logout, and what the site gate exempts."""
    return request.path in (
        reverse("pages:anonymous_answers"),
        reverse("account_logout"),
    ) or request.path.startswith(_gate_exempt_paths())


def resolve_identity(request) -> UserIdentity:
    """Resolve the UserIdentity that owns this request's data, creating it if
    needed."""
    if request.user.is_authenticated:
        return user_identity_ensure(user=request.user)
    if not request.session.session_key:
        request.session.create()
    identity, _ = UserIdentity.objects.get_or_create(
        user=None, session_key=request.session.session_key
    )
    return identity


class IdentityMiddleware:
    """Attach a lazy ``request.identity`` UserIdentity."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.identity = SimpleLazyObject(lambda: resolve_identity(request))
        return self.get_response(request)
