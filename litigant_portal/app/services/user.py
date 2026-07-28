import logging

from django.db import transaction

from litigant_portal.app.models import UserIdentity

logger = logging.getLogger(__name__)


def identity_ensure(*, user) -> UserIdentity:
    """Return the UserIdentity for an authenticated user, creating it if needed."""
    identity, _ = UserIdentity.objects.get_or_create(
        user=user, defaults={"session_key": ""}
    )
    return identity


@transaction.atomic
def identity_merge(
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


def identity_merge_anonymous(*, user, session_key: str) -> None:
    """On login, fold the anonymous identity for ``session_key`` into ``user``."""
    anon_identity = UserIdentity.objects.filter(
        session_key=session_key, user__isnull=True
    ).first()
    if anon_identity is None:
        return
    target_identity = identity_ensure(user=user)
    identity_merge(
        source_identity=anon_identity, target_identity=target_identity
    )
