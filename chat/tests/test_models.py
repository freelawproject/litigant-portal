"""
Tests for custom model behavior in chat app.

Only tests custom code - not Django built-ins like UUIDField, auto_now, etc.
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from chat.models import ChatSession, Message

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
