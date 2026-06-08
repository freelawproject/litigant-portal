from django.utils.functional import SimpleLazyObject

from litigant_portal.app.models import UserIdentity
from litigant_portal.app.services.identity import identity_ensure


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
