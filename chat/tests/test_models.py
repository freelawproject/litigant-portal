"""
Tests for custom model behavior in chat app.

Only tests custom code - not Django built-ins like UUIDField, auto_now, etc.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from chat.models import CaseInfo, ChatSession, Message, TimelineEvent

User = get_user_model()


class ChatSessionStrTests(TestCase):
    """Tests for ChatSession.__str__ custom formatting."""

    def test_str_includes_username_for_authenticated_user(self):
        """__str__ should show username, not just 'Anonymous'."""
        user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        session = ChatSession.objects.create(user=user)

        result = str(session)

        self.assertIn("testuser", result)
        self.assertNotIn("Anonymous", result)

    def test_str_shows_anonymous_when_no_user(self):
        """__str__ should show 'Anonymous' for sessions without user."""
        session = ChatSession.objects.create(session_key="abc123")

        result = str(session)

        self.assertIn("Anonymous", result)
        self.assertNotIn("testuser", result)


class MessageStrTests(TestCase):
    """Tests for Message.__str__ truncation logic at 50-char boundary."""

    def setUp(self):
        self.session = ChatSession.objects.create()

    def test_str_no_truncation_at_50_chars(self):
        """Content exactly 50 chars should NOT be truncated."""
        content_50 = "x" * 50
        message = Message.objects.create(
            session=self.session,
            data={"role": "user", "content": content_50},
        )

        result = str(message)

        self.assertIn(content_50, result)
        self.assertNotIn("...", result)

    def test_str_truncates_at_51_chars(self):
        """Content at 51 chars should be truncated."""
        content_51 = "x" * 51
        message = Message.objects.create(
            session=self.session,
            data={"role": "user", "content": content_51},
        )

        result = str(message)

        self.assertIn("...", result)
        # Should show first 50 chars + ellipsis
        self.assertIn("x" * 50, result)
        self.assertNotIn("x" * 51, result)

    def test_str_includes_role_prefix(self):
        """__str__ should include the message role."""
        message = Message.objects.create(
            session=self.session,
            data={"role": "assistant", "content": "Hello"},
        )

        result = str(message)

        self.assertIn("assistant", result)


class CaseInfoStrTests(TestCase):
    """Tests for CaseInfo.__str__ custom formatting."""

    def test_str_shows_case_type_and_username(self):
        user = User.objects.create_user(username="jane", password="testpass")
        case = CaseInfo.objects.create(
            user=user, data={"case_type": "Eviction"}
        )

        result = str(case)

        self.assertIn("Eviction", result)
        self.assertIn("jane", result)

    def test_str_shows_anonymous_when_no_user(self):
        case = CaseInfo.objects.create(
            session_key="abc123", data={"case_type": "Eviction"}
        )

        result = str(case)

        self.assertIn("Eviction", result)
        self.assertIn("Anonymous", result)

    def test_str_shows_unknown_when_no_case_type(self):
        case = CaseInfo.objects.create(data={})

        result = str(case)

        self.assertIn("Unknown", result)


class TimelineEventStrTests(TestCase):
    """Tests for TimelineEvent.__str__ display logic."""

    def setUp(self):
        self.case = CaseInfo.objects.create(data={})

    def test_str_uses_title_when_set(self):
        event = TimelineEvent.objects.create(
            case=self.case,
            event_type="upload",
            title="Lease agreement uploaded",
        )

        result = str(event)

        self.assertIn("Document Upload", result)
        self.assertIn("Lease agreement uploaded", result)

    def test_str_falls_back_to_content_when_no_title(self):
        event = TimelineEvent.objects.create(
            case=self.case,
            event_type="summary",
            content="User discussed eviction timeline with assistant",
        )

        result = str(event)

        self.assertIn("Chat Summary", result)
        self.assertIn("User discussed eviction timeline", result)

    def test_str_truncates_content_at_50_chars(self):
        long_content = "x" * 80
        event = TimelineEvent.objects.create(
            case=self.case,
            event_type="change",
            content=long_content,
        )

        result = str(event)

        self.assertIn("x" * 50, result)
        self.assertNotIn("x" * 51, result)
