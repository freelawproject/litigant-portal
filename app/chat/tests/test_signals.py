"""Tests for anonymous-to-authenticated data migration signal."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from chat.models import CaseInfo, ChatSession

User = get_user_model()


def _create_anonymous_session(client):
    """Create an anonymous session and store the key for migration.

    Simulates what happens in production: the middleware stores
    _anonymous_session_key in session data on each anonymous request,
    and cycle_key() preserves it across login.
    """
    session = client.session
    session.create()
    session["_anonymous_session_key"] = session.session_key
    session.save()
    # Set the session cookie so subsequent requests use this session
    cookie_name = settings.SESSION_COOKIE_NAME
    client.cookies[cookie_name] = session.session_key
    return session.session_key


@override_settings(
    ACCOUNT_EMAIL_VERIFICATION="none",
    ACCOUNT_AUTHENTICATION_METHOD="username",
)
class MigrateAnonymousDataTests(TestCase):
    """Tests for the user_logged_in signal handler."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    def test_migrates_anonymous_chat_sessions(self):
        """Anonymous chat sessions should be linked to user on login."""
        client = Client()
        session_key = _create_anonymous_session(client)

        chat_session = ChatSession.objects.create(session_key=session_key)

        client.login(username="testuser", password="testpass")

        chat_session.refresh_from_db()
        self.assertEqual(chat_session.user, self.user)
        self.assertEqual(chat_session.session_key, "")

    def test_migrates_anonymous_case_info(self):
        """Anonymous CaseInfo should be linked to user on login."""
        client = Client()
        session_key = _create_anonymous_session(client)

        case = CaseInfo.objects.create(
            session_key=session_key,
            data={"case_type": "Eviction"},
        )

        client.login(username="testuser", password="testpass")

        case.refresh_from_db()
        self.assertEqual(case.user, self.user)
        self.assertEqual(case.session_key, "")
        self.assertEqual(case.data["case_type"], "Eviction")

    def test_deletes_duplicate_anonymous_case(self):
        """If user already has CaseInfo, anonymous one is deleted."""
        client = Client()
        session_key = _create_anonymous_session(client)

        # User already has a case
        CaseInfo.objects.create(
            user=self.user,
            data={"case_type": "Foreclosure"},
        )
        # Anonymous case exists too
        CaseInfo.objects.create(
            session_key=session_key,
            data={"case_type": "Eviction"},
        )

        client.login(username="testuser", password="testpass")

        # User's existing case should remain
        self.assertEqual(CaseInfo.objects.count(), 1)
        remaining = CaseInfo.objects.first()
        self.assertEqual(remaining.user, self.user)
        self.assertEqual(remaining.data["case_type"], "Foreclosure")

    def test_noop_without_anonymous_data(self):
        """Login without anonymous data should not error."""
        client = Client()
        client.login(username="testuser", password="testpass")

        self.assertEqual(ChatSession.objects.count(), 0)
        self.assertEqual(CaseInfo.objects.count(), 0)

    def test_timeline_events_follow_case(self):
        """TimelineEvents should follow their CaseInfo to the user."""
        client = Client()
        session_key = _create_anonymous_session(client)

        case = CaseInfo.objects.create(
            session_key=session_key,
            data={"case_type": "Eviction"},
        )
        case.timeline_events.create(
            event_type="upload",
            title="Test upload",
            content="Test content",
        )

        client.login(username="testuser", password="testpass")

        case.refresh_from_db()
        self.assertEqual(case.user, self.user)
        self.assertEqual(case.timeline_events.count(), 1)
