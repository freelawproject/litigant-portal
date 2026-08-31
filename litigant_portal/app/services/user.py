import logging

from django.contrib.auth.models import Group, User
from django.db import transaction

from litigant_portal.app.models import UserIdentity
from litigant_portal.app.permissions import ADMINS_GROUP, DEVELOPERS_GROUP

logger = logging.getLogger(__name__)


def _group_toggle(*, user: User, name: str) -> bool:
    """Flip a user's membership in a group; returns the new state."""
    group = Group.objects.get(name=name)
    if user.groups.filter(pk=group.pk).exists():
        user.groups.remove(group)
        return False
    user.groups.add(group)
    return True


def user_admin_toggle(*, user: User) -> bool:
    """Flip a user's membership in the Admins group."""
    return _group_toggle(user=user, name=ADMINS_GROUP)


def user_developer_toggle(*, user: User) -> bool:
    """Flip a user's membership in the Developers group."""
    return _group_toggle(user=user, name=DEVELOPERS_GROUP)


def user_identity_ensure(*, user) -> UserIdentity:
    """Return the UserIdentity for an authenticated user, creating it if needed."""
    identity, _ = UserIdentity.objects.get_or_create(
        user=user, defaults={"session_key": ""}
    )
    return identity


def _variable_answers_migrate(
    *, source_identity: UserIdentity, target_identity: UserIdentity
) -> int:
    """Move ``source``'s answers to ``target``; returns how many moved.

    ``(identity, variable)`` is unique, so an answer both identities gave
    can't move. The target's wins: it belongs to the account being logged
    into, and dropping the anonymous one only re-asks a question, where
    overwriting a confirmed answer could prefill a court form with the
    wrong value. The losers stay on ``source`` and die with it via CASCADE.
    """
    answered = set(
        target_identity.variable_answers.values_list("variable_id", flat=True)
    )
    return source_identity.variable_answers.exclude(
        variable_id__in=answered
    ).update(identity=target_identity)


@transaction.atomic
def user_identity_merge(
    *, source_identity: UserIdentity, target_identity: UserIdentity
) -> None:
    """Fold ``source`` into ``target``, then delete ``source``.

    All chat threads and uploads migrate, as do variable answers the target
    hasn't answered itself. Runs in a single transaction.
    """
    threads = source_identity.chat_threads.update(identity=target_identity)
    uploads = source_identity.uploads.update(identity=target_identity)
    answers = _variable_answers_migrate(
        source_identity=source_identity, target_identity=target_identity
    )

    source_identity.delete()

    logger.info(
        "Merged anonymous identity into user %s: "
        "%d thread(s), %d upload(s), %d answer(s) migrated",
        target_identity.user_id,
        threads,
        uploads,
        answers,
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
