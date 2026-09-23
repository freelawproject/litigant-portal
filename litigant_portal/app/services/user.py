import logging

from django.contrib.auth.models import Group, User
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

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
    """
    Move unscoped answers and history, keeping target answers current.

    Supersede conflicting anonymous answers before transferring their owner.
    Matching uses the variable name across definition versions.
    """
    answered = set(
        target_identity.variable_answers.filter(
            matter__isnull=True, state="active"
        ).values_list("variable__name", flat=True)
    )
    source_identity.variable_answers.filter(
        matter__isnull=True, state="active", variable__name__in=answered
    ).update(state="superseded")
    return source_identity.variable_answers.filter(matter__isnull=True).update(
        identity=target_identity
    )


@transaction.atomic
def user_identity_merge(
    *, source_identity: UserIdentity, target_identity: UserIdentity
) -> None:
    """
    Transfer existing application records to the authenticated identity.

    Preserve the anonymous identity when immutable attribution refers to it.
    """
    threads = source_identity.chat_threads.update(identity=target_identity)
    uploads = source_identity.uploads.update(identity=target_identity)
    answers = _variable_answers_migrate(
        source_identity=source_identity, target_identity=target_identity
    )

    try:
        with transaction.atomic():
            source_identity.delete()
    except ProtectedError:
        UserIdentity.objects.filter(pk=source_identity.pk).update(
            session_key="",
            deleted_at=timezone.now(),
            updated_at=timezone.now(),
        )

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
