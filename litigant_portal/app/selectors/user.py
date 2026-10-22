from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group, User
from django.db.models import Exists, OuterRef, QuerySet

from litigant_portal.app.permissions import (
    ADMINS_GROUP,
    DEVELOPERS_GROUP,
    STAFF_GROUPS,
    USER_ADMINS_GROUP,
)


def _member_of(name: str) -> Exists:
    return Exists(Group.objects.filter(name=name, user=OuterRef("pk")))


def user_get(*, user_id: int) -> User:
    """A single user (raises User.DoesNotExist)."""
    return User.objects.get(id=user_id)


def user_list(
    *, search: str = "", app_users_only: bool = False
) -> QuerySet[User]:
    """Users for the admin users tab, filtered by email substring, each
    annotated with its group memberships.

    ``app_users_only`` leaves out staff (superusers, Django admin staff,
    Admins, Developers),
    which is all a user admin sees. Disabled accounts stay listed so they
    can be enabled again.
    """
    users = User.objects.order_by("email").annotate(
        is_admin_member=_member_of(ADMINS_GROUP),
        is_developer_member=_member_of(DEVELOPERS_GROUP),
        is_user_admin_member=_member_of(USER_ADMINS_GROUP),
    )
    if search:
        users = users.filter(email__icontains=search)
    if app_users_only:
        users = users.filter(is_superuser=False, is_staff=False).exclude(
            groups__name__in=STAFF_GROUPS
        )
    return users


def user_email_taken(*, email: str) -> bool:
    """Whether ``email`` is already in use, in any case.

    A new account stores it three times, as its email, its username, and
    allauth's address row, and each must be unique. Another account can hold
    it in any of them: allauth keeps an old address when Django admin
    changes an account's email.
    """
    return (
        User.objects.filter(email__iexact=email).exists()
        or User.objects.filter(username__iexact=email).exists()
        or EmailAddress.objects.filter(email__iexact=email).exists()
    )


def user_is_manageable(*, viewer: User, target: User) -> bool:
    """Whether ``viewer`` may reset, disable, enable, or delete ``target``.

    Staff are managed only from above: superusers, Django admin staff
    (``is_staff``, which can read every transcript there), and user admins
    by superusers; developers by those who manage developers; admins by
    those who manage the site. Every other account is an app user, open to
    anyone holding ``manage_app_users``.
    """
    if target.is_superuser or target.is_staff:
        return viewer.is_superuser
    groups = set(target.groups.values_list("name", flat=True))
    if DEVELOPERS_GROUP in groups:
        return viewer.has_perm("app.manage_developers")
    if ADMINS_GROUP in groups:
        return viewer.has_perm("app.manage_site")
    if USER_ADMINS_GROUP in groups:
        # Only a superuser touches a user admin, so one can't remove another
        # (#1073). Their own password is the exception; the views refuse the
        # rest as self-lockout.
        return viewer.is_superuser or viewer.pk == target.pk
    return viewer.has_perm("app.manage_app_users")
