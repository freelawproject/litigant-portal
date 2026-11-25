import secrets

from allauth.mfa.models import Authenticator
from allauth.mfa.utils import is_mfa_enabled
from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.functional import SimpleLazyObject
from django.utils.translation import gettext as _
from django_ratelimit.core import is_ratelimited

from litigant_portal.app.models import UserIdentity
from litigant_portal.app.services.user import user_identity_ensure
from litigant_portal.app.session import ANONYMOUS_SESSION_KEY
from litigant_portal.app.views.utils import needs_two_factor


def _gate_exempt_paths() -> tuple[str, ...]:
    """Path prefixes the site gate leaves alone: static files, media and
    the API."""
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
    """Carry the anonymous session's key across login.

    While the visitor is anonymous, their session key is copied into the
    session data. Django's ``login()`` rotates the key but keeps the data,
    so the copy survives for ``AccountAdapter.post_login`` to act on.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session = request.session
        if (
            not request.user.is_authenticated
            and session.session_key
            and session.get(ANONYMOUS_SESSION_KEY) != session.session_key
        ):
            session[ANONYMOUS_SESSION_KEY] = session.session_key
        return self.get_response(request)


def _two_factor_exempt_paths() -> tuple[str, ...]:
    """Path prefixes a staff account can open before two-factor is set
    up: the setup and confirm pages, sign out, and what every page needs
    to load."""
    return tuple(
        p
        for p in (
            reverse("mfa_activate_totp"),
            reverse("account_reauthenticate"),
            reverse("mfa_reauthenticate"),
            reverse("account_logout"),
            reverse("browser_log"),
            reverse("csp_report"),
            reverse("health"),
            "/i18n/",
            "/jsi18n/",
            settings.STATIC_URL,
            settings.MEDIA_URL,
        )
        if p
    )


class StaffTwoFactorMiddleware:
    """Send a staff account with no two-factor to the setup page. The
    API answers 403 instead. Any other account gets a 404 on the
    two-factor pages, unless it still has two-factor to turn off."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if not user.is_authenticated:
            return self.get_response(request)
        staff = needs_two_factor(user)
        if (
            not staff
            and request.path.startswith(reverse("mfa_index"))
            and not is_mfa_enabled(user, [Authenticator.Type.TOTP])
        ):
            raise Http404
        if (
            not settings.STAFF_TWO_FACTOR_REQUIRED
            or not staff
            or request.path.startswith(_two_factor_exempt_paths())
            or is_mfa_enabled(user, [Authenticator.Type.TOTP])
        ):
            return self.get_response(request)
        if request.path.startswith("/api/"):
            return JsonResponse(
                {"error": _("Set up two-factor sign-in first.")}, status=403
            )
        return redirect("mfa_activate_totp")


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
