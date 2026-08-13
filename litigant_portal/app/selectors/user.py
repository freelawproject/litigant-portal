from django.contrib.auth.models import Group, User
from django.db.models import Exists, OuterRef, QuerySet

from litigant_portal.app.models import UserIdentity
from litigant_portal.app.permissions import ADMINS_GROUP, DEVELOPERS_GROUP

SESSION_KEY_DISPLAY_CHARS = 8


def user_identity_session_key_short(*, identity: UserIdentity) -> str:
    """An identity's session key, truncated for display.

    ``session_key`` is the live value of the visitor's sessionid cookie, so no
    audit surface renders it whole. The full value stays in the database and in
    admin ``search_fields``, which is how staff already holding a key look a
    thread up; 8 characters is a hint, not a usable handle. Use
    ``UserIdentity.id`` to correlate threads to one visitor.
    """
    return identity.session_key[:SESSION_KEY_DISPLAY_CHARS]


def user_get(*, user_id: int) -> User:
    """A single user (raises User.DoesNotExist)."""
    return User.objects.get(id=user_id)


def user_list(*, search: str = "") -> QuerySet[User]:
    """Users for the admin users tab, filtered by email substring, each
    annotated with ``is_admin_member`` and ``is_developer_member``."""
    users = User.objects.order_by("email")
    if search:
        users = users.filter(email__icontains=search)
    return users.annotate(
        is_admin_member=Exists(
            Group.objects.filter(name=ADMINS_GROUP, user=OuterRef("pk"))
        ),
        is_developer_member=Exists(
            Group.objects.filter(name=DEVELOPERS_GROUP, user=OuterRef("pk"))
        ),
    )
