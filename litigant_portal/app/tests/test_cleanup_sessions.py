"""Tests for the cleanup_sessions management command."""

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from litigant_portal.app.models import (
    ChatMessage,
    ChatThread,
    UserIdentity,
    UserUpload,
)


def _run(*args):
    out = StringIO()
    call_command("cleanup_sessions", *args, stdout=out)
    return out.getvalue()


@pytest.mark.postgres
class CleanupSessionsTests(TestCase):
    def setUp(self):
        self.stale = UserIdentity.objects.create(session_key="stale")
        UserIdentity.objects.filter(pk=self.stale.pk).update(
            created_at=timezone.now() - timedelta(days=60)
        )
        self.thread = ChatThread.objects.create(identity=self.stale)
        self.upload = UserUpload.objects.create(
            identity=self.stale,
            file="uploads/x/notes.txt",
            name="notes.txt",
            content_type="text/plain",
            size=5,
        )
        self.fresh = UserIdentity.objects.create(session_key="fresh")

    def _add_message(self, days_ago=0):
        message = ChatMessage.objects.create(
            thread=self.thread, data={"role": "user", "content": "hi"}
        )
        ChatMessage.objects.filter(pk=message.pk).update(
            created_at=timezone.now() - timedelta(days=days_ago)
        )
        return message

    def test_dry_run_reports_counts_without_deleting(self):
        output = _run()
        self.assertIn("DRY RUN", output)
        self.assertIn("1 anonymous identities", output)
        self.assertIn("1 chat threads", output)
        self.assertIn("1 uploads", output)
        self.assertIn("30-day retention window", output)
        self.assertTrue(UserIdentity.objects.filter(pk=self.stale.pk).exists())

    def test_delete_removes_stale_identity_and_data(self):
        _run("--delete")
        self.assertFalse(
            UserIdentity.objects.filter(pk=self.stale.pk).exists()
        )
        self.assertFalse(ChatThread.objects.filter(pk=self.thread.pk).exists())
        self.assertFalse(UserUpload.objects.filter(pk=self.upload.pk).exists())
        self.assertTrue(UserIdentity.objects.filter(pk=self.fresh.pk).exists())

    def test_noop_when_nothing_is_stale(self):
        UserIdentity.objects.filter(pk=self.stale.pk).delete()
        output = _run()
        self.assertIn("No anonymous identities", output)

    def test_recent_chat_activity_keeps_old_identity(self):
        self._add_message(days_ago=1)
        _run("--delete")
        self.assertTrue(UserIdentity.objects.filter(pk=self.stale.pk).exists())
        self.assertTrue(ChatThread.objects.filter(pk=self.thread.pk).exists())

    def test_old_chat_activity_does_not_keep_identity(self):
        self._add_message(days_ago=45)
        _run("--delete")
        self.assertFalse(
            UserIdentity.objects.filter(pk=self.stale.pk).exists()
        )

    def test_identity_with_a_user_is_never_deleted(self):
        user = get_user_model().objects.create_user(
            username="litigant", password="pw"
        )
        owned = UserIdentity.objects.create(user=user)
        UserIdentity.objects.filter(pk=owned.pk).update(
            created_at=timezone.now() - timedelta(days=365)
        )
        _run("--delete")
        self.assertTrue(UserIdentity.objects.filter(pk=owned.pk).exists())

    def test_days_flag_cannot_shrink_the_audit_window(self):
        self._add_message(days_ago=10)
        output = _run("--days=7", "--delete")
        self.assertIn("below AUDIT_RETENTION_DAYS", output)
        self.assertTrue(UserIdentity.objects.filter(pk=self.stale.pk).exists())
        self.assertTrue(ChatThread.objects.filter(pk=self.thread.pk).exists())

    def test_small_days_flag_still_deletes_quiet_identities(self):
        self._add_message(days_ago=40)
        _run("--days=7", "--delete")
        self.assertFalse(
            UserIdentity.objects.filter(pk=self.stale.pk).exists()
        )

    def test_default_window_comes_from_settings(self):
        with override_settings(AUDIT_RETENTION_DAYS=15):
            output = _run()
        self.assertIn("15-day retention window", output)

    def test_days_flag_overrides_settings(self):
        output = _run("--days=200")
        self.assertIn("No anonymous identities", output)
        self.assertIn("200-day retention window", output)
