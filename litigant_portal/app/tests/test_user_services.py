"""Unit tests for the user identity services (services/user.py).

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
    Variable,
    VariableAnswer,
)
from litigant_portal.app.services.user import (
    user_identity_ensure,
    user_identity_merge,
    user_identity_merge_anonymous,
)

User = get_user_model()


@pytest.mark.postgres
class IdentityEnsureTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")

    def test_creates_identity_when_missing(self):
        identity = user_identity_ensure(user=self.user)
        self.assertEqual(identity.user, self.user)
        self.assertEqual(identity.session_key, "")

    def test_returns_existing_identity_without_duplicating(self):
        existing = UserIdentity.objects.create(user=self.user)
        self.assertEqual(user_identity_ensure(user=self.user), existing)
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
        user_identity_merge(
            source_identity=self.anon, target_identity=self.target
        )
        thread.refresh_from_db()
        upload.refresh_from_db()
        self.assertEqual(thread.identity, self.target)
        self.assertEqual(upload.identity, self.target)
        # The stored path is identity-free, so the merge never touches it.
        self.assertEqual(upload.file.name, "uploads/x/notes.txt")


@pytest.mark.postgres
class IdentityMergeVariableAnswerTests(TestCase):
    """Answers follow the identity on login, target winning any conflict."""

    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")
        self.target = UserIdentity.objects.create(user=self.user)
        self.anon = UserIdentity.objects.create(session_key="abc123")
        self.first_name = Variable.objects.create(name="first_name")
        self.city = Variable.objects.create(name="city")

    def _answer(self, identity, variable, value, reviewed=False):
        return VariableAnswer.objects.create(
            identity=identity,
            variable=variable,
            value=value,
            reviewed=reviewed,
        )

    def _merge(self):
        user_identity_merge(
            source_identity=self.anon, target_identity=self.target
        )

    def test_answers_migrate_with_value_and_reviewed_intact(self):
        confirmed = self._answer(
            self.anon, self.first_name, "Ada", reviewed=True
        )
        unconfirmed = self._answer(self.anon, self.city, "Fargo")

        self._merge()

        confirmed.refresh_from_db()
        unconfirmed.refresh_from_db()
        self.assertEqual(confirmed.identity, self.target)
        self.assertEqual(confirmed.value, "Ada")
        self.assertTrue(confirmed.reviewed)
        self.assertEqual(unconfirmed.identity, self.target)
        self.assertFalse(unconfirmed.reviewed)
        self.assertFalse(UserIdentity.objects.filter(pk=self.anon.pk).exists())

    def test_conflict_keeps_the_target_answer(self):
        # Source is the confirmed one, so a source overwrite would be visible
        # in both value and reviewed.
        self._answer(self.anon, self.first_name, "Guest", reviewed=True)
        kept = self._answer(self.target, self.first_name, "Ada")

        self._merge()

        kept.refresh_from_db()
        self.assertEqual(kept.value, "Ada")
        self.assertFalse(kept.reviewed)
        self.assertEqual(
            VariableAnswer.objects.filter(variable=self.first_name).count(), 1
        )

    def test_conflict_does_not_block_a_sibling_answer(self):
        self._answer(self.anon, self.first_name, "Guest")
        self._answer(self.target, self.first_name, "Ada")
        moved = self._answer(self.anon, self.city, "Fargo")

        self._merge()

        moved.refresh_from_db()
        self.assertEqual(moved.identity, self.target)
        self.assertEqual(VariableAnswer.objects.count(), 2)

    def test_log_reports_the_migrated_answer_count(self):
        self._answer(self.anon, self.first_name, "Ada")
        self._answer(self.target, self.city, "Fargo")
        self._answer(self.anon, self.city, "Bismarck")

        with self.assertLogs(
            "litigant_portal.app.services.user", level="INFO"
        ) as logs:
            self._merge()

        # Only the non-conflicting answer counts as migrated.
        self.assertIn("1 answer(s)", logs.output[0])


@pytest.mark.postgres
class IdentityAbsorbAnonymousTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")

    def test_noop_when_no_anonymous_identity(self):
        user_identity_merge_anonymous(user=self.user, session_key="missing")
        self.assertFalse(UserIdentity.objects.filter(user=self.user).exists())

    def test_ignores_logged_in_identity_sharing_the_session_key(self):
        # A user-owned identity must never be treated as anonymous, even if it
        # somehow shares the session key — guards the user__isnull filter.
        UserIdentity.objects.create(user=self.user, session_key="abc123")
        user_identity_merge_anonymous(user=self.user, session_key="abc123")
        self.assertEqual(
            UserIdentity.objects.filter(user=self.user).count(), 1
        )
