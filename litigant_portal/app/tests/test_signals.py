"""End-to-end coverage for the anonymous-to-authenticated merge signal.

The merge *logic* is unit-tested in test_identity_services.py. These tests
cover only what those can't: that the signal is actually wired to login, and
that the request-bound session key is read correctly across cycle_key().
"""

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from litigant_portal.app.models import CaseInfo, ChatSession, UserIdentity

User = get_user_model()


def _create_anonymous_session(client):
    """Create an anonymous session and store the key for migration.

    Simulates production: the middleware stores _anonymous_session_key in
    session data on each anonymous request, and cycle_key() preserves it
    across login.
    """
    session = client.session
    session.create()
    session["_anonymous_session_key"] = session.session_key
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
    return session.session_key


@pytest.mark.postgres
@override_settings(
    ACCOUNT_EMAIL_VERIFICATION="none",
    ACCOUNT_AUTHENTICATION_METHOD="username",
)
class MergeAnonymousIdentitySignalTests(TestCase):
    """The signal wiring and request-key glue — not the merge logic itself."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    def test_login_migrates_anonymous_data(self):
        """Logging in fires the signal and folds anon data into the user."""
        client = Client()
        session_key = _create_anonymous_session(client)
        anon = UserIdentity.objects.create(session_key=session_key)
        chat = ChatSession.objects.create(identity=anon)
        case = CaseInfo.objects.create(
            identity=anon, data={"case_type": "Eviction"}
        )

        client.login(username="testuser", password="testpass")

        chat.refresh_from_db()
        case.refresh_from_db()
        self.assertEqual(chat.identity.user, self.user)
        self.assertEqual(case.identity.user, self.user)

    def test_login_without_anonymous_data_is_safe(self):
        """No anonymous key in the session → no-op, no error."""
        client = Client()
        client.login(username="testuser", password="testpass")

        self.assertEqual(ChatSession.objects.count(), 0)
        self.assertEqual(CaseInfo.objects.count(), 0)
