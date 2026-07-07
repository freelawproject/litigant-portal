from django.conf import settings
from django.shortcuts import redirect, render
from django.utils.functional import SimpleLazyObject

from litigant_portal.app.models import UserIdentity
from litigant_portal.app.services.identity import identity_ensure


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
            or request.path.startswith(
                (settings.STATIC_URL, settings.MEDIA_URL, "/api/")
            )
        ):
            return self.get_response(request)
        # This runs before CsrfViewMiddleware's view check, so the POST needs
        # no CSRF token.
        if request.method == "POST" and "site_password" in request.POST:
            if request.POST["site_password"] == password:
                request.session[self.SESSION_KEY] = True
                return redirect(request.path)
            return render(
                request, "site_password.html", {"error": True}, status=401
            )
        return render(request, "site_password.html", status=401)


class AnonymousSessionKeyMiddleware:
    """Save the anonymous session key so the login signal can migrate data."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        session = request.session
        if (
            not request.user.is_authenticated
            and session.session_key
            and session.get("_anonymous_session_key") != session.session_key
        ):
            session["_anonymous_session_key"] = session.session_key
        return self.get_response(request)


def resolve_identity(request) -> UserIdentity:
    """Resolve the UserIdentity that owns this request's data, creating it if
    needed."""
    if request.user.is_authenticated:
        return identity_ensure(user=request.user)
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
