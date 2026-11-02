from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group, User
from django.db.models import Exists, OuterRef, QuerySet

from litigant_portal.app.permissions import (
    COURT_ADMINS_GROUP,
    FLP_STAFF_GROUP,
    Tier,
)


def _member_of(name: str) -> Exists:
    return Exists(Group.objects.filter(name=name, user=OuterRef("pk")))


def user_get(*, user_id: int) -> User:
    """A single user (raises User.DoesNotExist)."""
    return User.objects.get(id=user_id)


def user_list(
    *, search: str = "", max_tier: Tier = Tier.SUPERUSER
) -> QuerySet[User]:
    """Users for the admin users tab, filtered by email substring, each
    annotated with its role memberships.

    ``max_tier`` is the highest tier listed: a viewer sees their own tier
    and below, so a Court Admin never sees FLP Staff and only a superuser
    sees superusers. Disabled accounts stay listed so they can be enabled
    again.
    """
    users = User.objects.order_by("email").annotate(
        is_flp_staff_member=_member_of(FLP_STAFF_GROUP),
        is_court_admin_member=_member_of(COURT_ADMINS_GROUP),
    )
    if search:
        users = users.filter(email__icontains=search)
    if max_tier < Tier.SUPERUSER:
        users = users.filter(is_superuser=False)
    if max_tier < Tier.FLP_STAFF:
        users = users.filter(is_staff=False, is_flp_staff_member=False)
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


def user_tier(*, user: User) -> Tier:
    """The account's tier (#1135), read from the account itself.

    Not from ``has_perm``, which answers False for a disabled account and
    would drop a disabled FLP Staff account into a Court Admin's reach.
    Django admin staff (``is_staff``, which can read every transcript
    there) rank as FLP Staff even without the group. Uses the
    ``user_list`` annotations when the row has them.
    """
    if user.is_superuser:
        return Tier.SUPERUSER
    if hasattr(user, "is_flp_staff_member"):
        flp_staff = user.is_flp_staff_member
        court_admin = user.is_court_admin_member
    else:
        groups = set(user.groups.values_list("name", flat=True))
        flp_staff = FLP_STAFF_GROUP in groups
        court_admin = COURT_ADMINS_GROUP in groups
    if user.is_staff or flp_staff:
        return Tier.FLP_STAFF
    if court_admin:
        return Tier.COURT_ADMIN
    return Tier.APP_USER


def user_is_manageable(*, viewer: User, target: User) -> bool:
    """Whether ``viewer`` may reset, disable, enable, or delete ``target``:
    only an account in a lower tier, so never one's own tier or oneself.
    Holding ``app.manage_app_users`` is the view's guard, not this one's."""
    return user_tier(user=viewer) > user_tier(user=target)


def user_assignable_roles(*, viewer: User) -> list[Tier]:
    """The roles ``viewer`` may give an account, highest first: every tier
    below their own. Superuser is never one; that's infra's to grant."""
    tier = user_tier(user=viewer)
    return [t for t in reversed(Tier) if t < tier and t < Tier.SUPERUSER]
