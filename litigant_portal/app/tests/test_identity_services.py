"""Unit tests for the identity services.

These exercise the core logic directly — no HTTP client, no login flow —
which is the payoff of moving the merge out of the signal handler. The
end-to-end signal path stays covered by test_signals.py.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from litigant_portal.app.models import CaseInfo, ChatSession, UserIdentity
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

    def test_migrates_chat_sessions_and_deletes_source(self):
        chat = ChatSession.objects.create(identity=self.anon)
        identity_merge(source_identity=self.anon, target_identity=self.target)
        chat.refresh_from_db()
        self.assertEqual(chat.identity, self.target)
        self.assertFalse(UserIdentity.objects.filter(pk=self.anon.pk).exists())

    def test_migrates_anonymous_case_and_its_children(self):
        case = CaseInfo.objects.create(
            identity=self.anon, data={"case_type": "Eviction"}
        )
        case.timeline_events.create(event_type="upload", title="Receipt")
        identity_merge(source_identity=self.anon, target_identity=self.target)
        case.refresh_from_db()
        self.assertEqual(case.identity, self.target)
        # Children hang off the case, not the identity, so they follow it.
        self.assertEqual(case.timeline_events.count(), 1)

    def test_drops_duplicate_active_case_keeping_target(self):
        CaseInfo.objects.create(
            identity=self.target,
            status="active",
            data={"case_type": "Foreclosure"},
        )
        CaseInfo.objects.create(
            identity=self.anon,
            status="active",
            data={"case_type": "Eviction"},
        )
        identity_merge(source_identity=self.anon, target_identity=self.target)
        cases = CaseInfo.objects.all()
        self.assertEqual(cases.count(), 1)
        self.assertEqual(cases.first().data["case_type"], "Foreclosure")

    def test_migrates_non_active_case_even_when_target_has_active(self):
        # The case the old signal silently cascade-dropped.
        CaseInfo.objects.create(
            identity=self.target,
            status="active",
            data={"case_type": "Foreclosure"},
        )
        CaseInfo.objects.create(
            identity=self.anon,
            status="archived",
            data={"case_type": "Eviction"},
        )
        identity_merge(source_identity=self.anon, target_identity=self.target)
        archived = CaseInfo.objects.get(status="archived")
        self.assertEqual(archived.identity, self.target)


@pytest.mark.postgres
class IdentityAbsorbAnonymousTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")

    def test_noop_when_no_anonymous_identity(self):
        identity_merge_anonymous(user=self.user, session_key="missing")
        self.assertFalse(UserIdentity.objects.filter(user=self.user).exists())

    def test_absorbs_anonymous_data_into_user(self):
        anon = UserIdentity.objects.create(session_key="abc123")
        ChatSession.objects.create(identity=anon)
        identity_merge_anonymous(user=self.user, session_key="abc123")
        target = UserIdentity.objects.get(user=self.user)
        self.assertEqual(target.chat_sessions.count(), 1)
        self.assertFalse(UserIdentity.objects.filter(pk=anon.pk).exists())

    def test_ignores_logged_in_identity_sharing_the_session_key(self):
        # A user-owned identity must never be treated as anonymous, even if it
        # somehow shares the session key — guards the user__isnull filter.
        UserIdentity.objects.create(user=self.user, session_key="abc123")
        identity_merge_anonymous(user=self.user, session_key="abc123")
        self.assertEqual(
            UserIdentity.objects.filter(user=self.user).count(), 1
        )
