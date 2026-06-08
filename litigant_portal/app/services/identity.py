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

    All chat sessions migrate. For cases, an identity is assumed to hold at
    most one active case: if ``target`` already has one, ``source``'s active
    case is dropped as a duplicate. Every other case (resolved/archived)
    migrates regardless. Runs in a single transaction.
    """
    chats = source_identity.chat_sessions.update(identity=target_identity)

    dropped = 0
    if target_identity.case_infos.filter(status="active").exists():
        duplicates = source_identity.case_infos.filter(status="active")
        dropped = duplicates.count()
        duplicates.delete()
    cases = source_identity.case_infos.update(identity=target_identity)

    source_identity.delete()

    logger.info(
        "Merged anonymous identity into user %s: %d chat session(s), "
        "%d case(s) migrated, %d duplicate active case(s) dropped",
        target_identity.user_id,
        chats,
        cases,
        dropped,
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
