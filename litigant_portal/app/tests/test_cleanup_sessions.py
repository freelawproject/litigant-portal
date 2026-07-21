"""Tests for the cleanup_sessions management command."""

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from litigant_portal.app.models import ChatThread, UserIdentity, UserUpload


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

    def test_dry_run_reports_counts_without_deleting(self):
        output = _run()
        self.assertIn("DRY RUN", output)
        self.assertIn("1 anonymous identities", output)
        self.assertIn("1 chat threads", output)
        self.assertIn("1 uploads", output)
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
