from litigant_portal.app.models import UserIdentity


def get_user_identity(request) -> UserIdentity:
    """Return the UserIdentity for the current request.

    Authenticated users get a UserIdentity row keyed to their User account.
    Anonymous users get one keyed to their session id (a session is created
    on demand if Django hasn't issued one yet). In both cases the identity
    is created on first use.
    """
    if request.user.is_authenticated:
        uid, _ = UserIdentity.objects.get_or_create(user=request.user)
        return uid

    if not request.session.session_key:
        # Force Django to mint a session id we can hang an identity off.
        request.session.save()
    uid, _ = UserIdentity.objects.get_or_create(
        user=None, session_id=request.session.session_key
    )
    return uid
