"""Signals for migrating anonymous data to authenticated users."""

import logging

from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .models import CaseInfo, ChatSession

logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def migrate_anonymous_data(request, user, **kwargs):
    """Migrate ChatSession and CaseInfo from anonymous session to user.

    When a user logs in, any data created during their anonymous session
    (identified by session_key) gets transferred to their user account.
    If the user already has a CaseInfo, the anonymous one is deleted to
    avoid duplicates.
    """
    # login() calls session.cycle_key() before this signal fires,
    # so session_key is the new one. The middleware saved the original
    # anonymous key as session data (which survives cycle_key).
    session_key = request.session.pop("_anonymous_session_key", None)
    if not session_key:
        return

    # Migrate chat sessions
    anonymous_sessions = ChatSession.objects.filter(
        session_key=session_key, user__isnull=True
    )
    migrated_chats = anonymous_sessions.update(user=user, session_key="")
    if migrated_chats:
        logger.info(
            "Migrated %d chat session(s) for user %s", migrated_chats, user
        )

    # Migrate case info
    anonymous_case = CaseInfo.objects.filter(
        session_key=session_key, user__isnull=True
    ).first()

    if not anonymous_case:
        return

    existing_case = CaseInfo.objects.filter(user=user).first()
    if existing_case:
        # User already has case info — delete the anonymous one
        anonymous_case.delete()
        logger.info("Deleted duplicate anonymous CaseInfo for user %s", user)
    else:
        anonymous_case.user = user
        anonymous_case.session_key = ""
        anonymous_case.save(update_fields=["user", "session_key"])
        logger.info("Migrated CaseInfo to user %s", user)
