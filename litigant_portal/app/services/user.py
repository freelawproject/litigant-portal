import logging

from django.contrib.auth.models import Group, User
from django.db import transaction

from litigant_portal.app.models import UserIdentity

logger = logging.getLogger(__name__)

ADMINS_GROUP = "Admins"
DEVELOPERS_GROUP = "Developers"


def user_admin_toggle(*, user: User) -> bool:
    """Flip a user's membership in the Admins group."""
    group = Group.objects.get(name=ADMINS_GROUP)
    if user.groups.filter(pk=group.pk).exists():
        user.groups.remove(group)
        return False
    user.groups.add(group)
    return True


def user_developer_toggle(*, user: User) -> bool:
    """Flip a user's membership in the Developers group."""
    group = Group.objects.get(name=DEVELOPERS_GROUP)
    if user.groups.filter(pk=group.pk).exists():
        user.groups.remove(group)
        return False
    user.groups.add(group)
    return True


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
