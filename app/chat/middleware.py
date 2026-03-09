"""Middleware for preserving anonymous session key across login."""


class AnonymousSessionKeyMiddleware:
    """Save the anonymous session key so the login signal can migrate data.

    Django's login() calls session.cycle_key(), which changes the session
    key but preserves session data. By storing the key as session data,
    the user_logged_in signal handler can find anonymous records to
    migrate.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            hasattr(request, "session")
            and hasattr(request, "user")
            and not request.user.is_authenticated
            and request.session.session_key
        ):
            request.session["_anonymous_session_key"] = (
                request.session.session_key
            )
        return self.get_response(request)
