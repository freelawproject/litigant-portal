import logging

from django.contrib.auth.models import User
from django.db import transaction

from litigant_portal.app.models import Site, SiteMembership, UserIdentity

logger = logging.getLogger(__name__)


def user_can_access_admin(*, user) -> bool:
    """Whether a user may see the admin panel at all.

    Developers (User.is_staff) always can; everyone else needs a membership in
    the currently active site.
    """
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return SiteMembership.objects.filter(user=user, site__active=True).exists()


def user_is_developer(*, user) -> bool:
    """Whether a user is a developer."""
    return user.is_authenticated and user.is_staff


def user_can_manage_site(*, user, site: Site) -> bool:
    """Whether a user may read or edit ``site`` itself."""
    if user.is_staff:
        return True
    return SiteMembership.objects.filter(user=user, site=site).exists()


def site_membership_toggle(*, user: User, site: Site) -> bool:
    """Flip a user's membership in ``site``; returns the new state."""
    membership = SiteMembership.objects.filter(user=user, site=site).first()
    if membership:
        membership.delete()
        return False
    SiteMembership.objects.create(user=user, site=site)
    return True


def user_developer_toggle(*, user: User) -> bool:
    """Flip a user's developer (staff) flag; returns the new state."""
    user.is_staff = not user.is_staff
    user.save(update_fields=["is_staff"])
    return user.is_staff


def user_identity_ensure(*, user) -> UserIdentity:
    """Return the UserIdentity for an authenticated user, creating it if needed."""
    identity, _ = UserIdentity.objects.get_or_create(
        user=user, defaults={"session_key": ""}
    )
    return identity


@transaction.atomic
def user_identity_merge(
    *, source_identity: UserIdentity, target_identity: UserIdentity
) -> None:
    """Fold ``source`` into ``target``, then delete ``source``.

    All chat threads and uploads migrate. Runs in a single transaction.
    """
    threads = source_identity.chat_threads.update(identity=target_identity)
    uploads = source_identity.uploads.update(identity=target_identity)

    source_identity.delete()

    logger.info(
        "Merged anonymous identity into user %s: "
        "%d thread(s), %d upload(s) migrated",
        target_identity.user_id,
        threads,
        uploads,
    )


def user_identity_merge_anonymous(*, user, session_key: str) -> None:
    """On login, fold the anonymous identity for ``session_key`` into ``user``."""
    anon_identity = UserIdentity.objects.filter(
        session_key=session_key, user__isnull=True
    ).first()
    if anon_identity is None:
        return
    target_identity = user_identity_ensure(user=user)
    user_identity_merge(
        source_identity=anon_identity, target_identity=target_identity
    )
