from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .services.identity import identity_merge_anonymous


@receiver(user_logged_in)
def merge_anonymous_identity(request, user, **kwargs):
    """On login, fold the anonymous UserIdentity into the user's identity."""
    session_key = request.session.pop("_anonymous_session_key", None)
    if session_key:
        identity_merge_anonymous(user=user, session_key=session_key)
