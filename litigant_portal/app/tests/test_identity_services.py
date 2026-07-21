"""Unit tests for the identity services.

These exercise the core logic directly — no HTTP client, no login flow —
which is the payoff of moving the merge out of the signal handler. The
end-to-end signal path stays covered by test_signals.py.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from litigant_portal.app.models import (
    ChatThread,
    UserIdentity,
    UserUpload,
)
from litigant_portal.app.services.identity import (
    identity_ensure,
    identity_merge,
    identity_merge_anonymous,
)

User = get_user_model()


@pytest.mark.postgres
class IdentityEnsureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")

    def test_creates_identity_when_missing(self):
        identity = identity_ensure(user=self.user)
        self.assertEqual(identity.user, self.user)
        self.assertEqual(identity.session_key, "")

    def test_returns_existing_identity_without_duplicating(self):
        existing = UserIdentity.objects.create(user=self.user)
        self.assertEqual(identity_ensure(user=self.user), existing)
        self.assertEqual(
            UserIdentity.objects.filter(user=self.user).count(), 1
        )


@pytest.mark.postgres
class IdentityMergeTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")
        self.target = UserIdentity.objects.create(user=self.user)
        self.anon = UserIdentity.objects.create(session_key="abc123")

    def test_migrates_chat_threads_and_uploads(self):
        thread = ChatThread.objects.create(identity=self.anon)
        upload = UserUpload.objects.create(
            identity=self.anon,
            file="uploads/x/notes.txt",
            name="notes.txt",
            content_type="text/plain",
            size=5,
        )
        identity_merge(source_identity=self.anon, target_identity=self.target)
        thread.refresh_from_db()
        upload.refresh_from_db()
        self.assertEqual(thread.identity, self.target)
        self.assertEqual(upload.identity, self.target)
        # The stored path is identity-free, so the merge never touches it.
        self.assertEqual(upload.file.name, "uploads/x/notes.txt")


@pytest.mark.postgres
class IdentityAbsorbAnonymousTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")

    def test_noop_when_no_anonymous_identity(self):
        identity_merge_anonymous(user=self.user, session_key="missing")
        self.assertFalse(UserIdentity.objects.filter(user=self.user).exists())

    def test_ignores_logged_in_identity_sharing_the_session_key(self):
        # A user-owned identity must never be treated as anonymous, even if it
        # somehow shares the session key — guards the user__isnull filter.
        UserIdentity.objects.create(user=self.user, session_key="abc123")
        identity_merge_anonymous(user=self.user, session_key="abc123")
        self.assertEqual(
            UserIdentity.objects.filter(user=self.user).count(), 1
        )
