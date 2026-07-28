from django.contrib.auth.models import Group, User
from django.db.models import Exists, OuterRef, QuerySet

from litigant_portal.app.services.user import (
    ADMINS_GROUP,
    DEVELOPERS_GROUP,
)


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
