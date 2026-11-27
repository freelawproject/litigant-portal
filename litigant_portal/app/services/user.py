import logging

from allauth.account.forms import ResetPasswordForm
from allauth.account.models import EmailAddress
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet

from litigant_portal.app.models import ChatThread, UserIdentity, UserUpload
from litigant_portal.app.permissions import (
    COURT_ADMINS_GROUP,
    FLP_STAFF_GROUP,
    Tier,
)
from litigant_portal.app.selectors.user import (
    user_identity_anonymous_find,
    user_identity_counts,
    user_identity_find,
)

logger = logging.getLogger(__name__)


_ROLE_GROUPS = {
    Tier.FLP_STAFF: FLP_STAFF_GROUP,
    Tier.COURT_ADMIN: COURT_ADMINS_GROUP,
}


@transaction.atomic
def user_role_set(*, user: User, role: Tier) -> None:
    """Put an account in exactly one role (#1135). FLP Staff also get
    Django admin staff access, which is how they read transcripts; every
    other role loses it. Who may give which role is the view's check."""
    if role == Tier.SUPERUSER:
        raise ValueError("Superuser is granted by infra, not assigned")
    user.groups.remove(*Group.objects.filter(name__in=_ROLE_GROUPS.values()))
    if role in _ROLE_GROUPS:
        user.groups.add(Group.objects.get(name=_ROLE_GROUPS[role]))
    user.is_staff = role == Tier.FLP_STAFF
    user.save(update_fields=["is_staff"])


@transaction.atomic
def user_create(
    *, email: str, password: str | None = None, role: Tier = Tier.APP_USER
) -> User:
    """Create an account in ``role``, with the password an admin set or,
    without one, no usable password until the invite link sets it. The
    address is recorded as verified the way ``bootstrap_superuser`` does
    it.
    """
    user = User.objects.create_user(
        username=email, email=email, password=password
    )
    EmailAddress.objects.create(
        user=user, email=email, verified=True, primary=True
    )
    if role != Tier.APP_USER:
        user_role_set(user=user, role=role)
    return user


def user_password_link_send(*, user: User, request) -> None:
    """Email ``user`` a link to set their password: the invite while the
    account has no password, a reset after. Raises ``ValidationError``
    when the address does not reach this account, and when sending
    fails."""
    form = ResetPasswordForm(data={"email": user.email})
    if not form.is_valid() or user not in form.users:
        raise ValidationError("This address does not reach the account")
    form.save(request)


def user_password_set(*, user: User, password: str) -> None:
    """Set a new password for an account."""
    user.set_password(password)
    user.save(update_fields=["password"])


def user_active_set(*, user: User, active: bool) -> None:
    """Disable or re-enable an account. A disabled account can't log in,
    and everything it owns stays."""
    user.is_active = active
    user.save(update_fields=["is_active"])


@transaction.atomic
def user_delete(*, user: User) -> None:
    """Delete an account and everything it owns, stored upload files
    included. Permanent."""
    user_identities_delete(identities=UserIdentity.objects.filter(user=user))
    user.delete()


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

    All chat threads and uploads migrate, as do variable answers and flow
    views the target does not have. Lock both owners so state writes and
    deletion cannot race with the transfer.
    """
    locked = _identities_lock(
        UserIdentity.objects.filter(
            pk__in=[source_identity.pk, target_identity.pk]
        )
    )
    if source_identity.pk not in locked:
        return
    if target_identity.pk not in locked:
        raise UserIdentity.DoesNotExist(
            "The target identity no longer exists."
        )
    threads = source_identity.chat_threads.update(identity=target_identity)
    uploads = source_identity.uploads.update(identity=target_identity)
    answers = _variable_answers_migrate(
        source_identity=source_identity, target_identity=target_identity
    )
    source_identity.flow_views.exclude(
        flow_id__in=target_identity.flow_views.values("flow_id")
    ).update(identity=target_identity)

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
    """Fold the anonymous identity for ``session_key`` into ``user``."""
    anon_identity = user_identity_anonymous_find(session_key=session_key)
    if anon_identity is None:
        return
    target_identity = user_identity_ensure(user=user)
    user_identity_merge(
        source_identity=anon_identity, target_identity=target_identity
    )


_NO_COUNTS = {"answers": 0, "threads": 0, "uploads": 0}


@transaction.atomic
def user_identity_anonymous_settle(
    *, user, session_key: str
) -> dict[str, int]:
    """What the anonymous identity for ``session_key`` still holds: the
    answers, threads and uploads ``user`` may bring into their account,
    all zero on a miss. Answers the account already gave are not counted,
    since a merge would drop them. An identity that holds nothing is
    deleted on the way, since no choice is needed for it. The identity is
    locked before the count, so a write still in flight for it is counted
    or waits."""
    anon_identity = user_identity_anonymous_find(session_key=session_key)
    if anon_identity is None:
        return dict(_NO_COUNTS)
    identities = UserIdentity.objects.filter(pk=anon_identity.pk)
    _identities_lock(identities)
    counts = user_identity_counts(
        identity=anon_identity, target_identity=user_identity_find(user=user)
    )
    if not any(counts.values()):
        user_identities_delete(identities=identities)
    return counts


def user_identity_delete_anonymous(
    *, user, session_key: str
) -> dict[str, int]:
    """Delete the anonymous identity for ``session_key`` and everything it
    owns: ``user`` chose not to bring it into their account.
    Returns the answers, threads and uploads it held, all zero on a miss."""
    anon_identity = user_identity_anonymous_find(session_key=session_key)
    if anon_identity is None:
        return dict(_NO_COUNTS)
    counts = user_identity_counts(identity=anon_identity)
    user_identities_delete(
        identities=UserIdentity.objects.filter(pk=anon_identity.pk)
    )
    logger.info(
        "Discarded anonymous identity for user %s: "
        "%d answer(s), %d thread(s), %d upload(s)",
        user.pk,
        counts["answers"],
        counts["threads"],
        counts["uploads"],
    )
    return counts


@transaction.atomic
def user_identity_reset(*, identity: UserIdentity) -> None:
    """Delete everything an identity owns: chat threads (their messages go
    with them), uploads with their stored files, and answers.

    Backs the dev and QA "Start over" control (#969), which returns a
    session to the seeded defaults. Seeded data (topics, flows, variables) belongs
    to no identity, so it stays. The identity row stays too, so the session
    or signed-in user keeps working.
    """
    if not _identities_lock(UserIdentity.objects.filter(pk=identity.pk)):
        return
    _uploads_delete(identity.uploads.all())
    identity.chat_threads.all().delete()
    identity.variable_answers.all().delete()
    identity.flow_views.all().delete()


@transaction.atomic
def user_identities_delete(
    *, identities: QuerySet[UserIdentity]
) -> tuple[int, int, int]:
    """Delete identities and everything they own, stored upload files
    included. ``identities`` is re-run under lock, so a row that stopped
    matching is kept. Returns (identities, threads, uploads) deleted."""
    locked = _identities_lock(identities)
    pks = list(identities.filter(pk__in=locked).values_list("pk", flat=True))
    upload_count = _uploads_delete(UserUpload.objects.filter(identity__in=pks))
    _, deleted = UserIdentity.objects.filter(pk__in=pks).delete()
    return (
        deleted.get(UserIdentity._meta.label, 0),
        deleted.get(ChatThread._meta.label, 0),
        upload_count,
    )


def _identities_lock(identities: QuerySet[UserIdentity]) -> list:
    """Lock the identities and their threads, so new uploads, threads and
    messages for them wait on the commit. Returns the identity pks."""
    pks = list(
        identities.order_by("pk")
        .select_for_update()
        .values_list("pk", flat=True)
    )
    threads = ChatThread.objects.filter(identity__in=pks).select_for_update()
    list(threads.values_list("pk", flat=True))
    return pks


def _uploads_delete(uploads: QuerySet[UserUpload]) -> int:
    """Delete upload rows now and their stored files once committed.
    Returns the number of uploads deleted."""
    files = list(uploads.exclude(file="").values_list("pk", "file"))
    _, deleted = uploads.delete()
    transaction.on_commit(lambda: _upload_files_delete(files))
    return deleted.get(UserUpload._meta.label, 0)


def _upload_files_delete(files: list[tuple]) -> None:
    """Delete stored files once their rows are committed gone. A failure
    leaves an orphaned file, which is harmless, so it is logged and the
    rest still go. Logs the upload id, not the name, which may identify
    the visitor."""
    storage = UserUpload._meta.get_field("file").storage
    for upload_id, name in files:
        try:
            storage.delete(name)
        except Exception:
            logger.exception(
                "Could not delete stored file of upload %s", upload_id
            )
