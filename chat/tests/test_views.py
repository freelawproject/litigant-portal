"""
Tests for chat views - custom validation and business logic.

Only tests custom code, not Django built-ins like @require_POST.
"""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from chat.models import ChatSession, Document, Message

User = get_user_model()


class SendMessageValidationTests(TestCase):
    """Tests for custom message validation in send_message view."""

    def setUp(self):
        self.client = Client()

    def test_rejects_empty_message(self):
        """Empty messages should be rejected with 400."""
        response = self.client.post("/chat/send/", {"message": ""})

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_rejects_whitespace_only_message(self):
        """Whitespace-only messages should be rejected."""
        response = self.client.post("/chat/send/", {"message": "   "})

        self.assertEqual(response.status_code, 400)

    def test_rejects_message_over_2000_chars(self):
        """Messages over 2000 characters should be rejected."""
        long_message = "x" * 2001
        response = self.client.post("/chat/send/", {"message": long_message})

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("2000", data["error"])

    def test_accepts_message_at_2000_chars(self):
        """Messages exactly 2000 characters should be accepted."""
        max_message = "x" * 2000
        response = self.client.post("/chat/send/", {"message": max_message})

        self.assertEqual(response.status_code, 200)


class SendMessageSessionTests(TestCase):
    """Tests for session management in send_message view."""

    def setUp(self):
        self.client = Client()

    def test_returns_session_and_message_ids(self):
        """Successful POST returns both IDs for client to use."""
        response = self.client.post("/chat/send/", {"message": "Hello"})

        data = json.loads(response.content)
        self.assertIn("session_id", data)
        self.assertIn("message_id", data)
        # IDs should be valid UUIDs (36 chars with hyphens)
        self.assertEqual(len(data["session_id"]), 36)
        self.assertEqual(len(data["message_id"]), 36)

    def test_creates_message_with_user_content(self):
        """The message content should match what was sent."""
        self.client.post("/chat/send/", {"message": "Test message content"})

        message = Message.objects.first()
        self.assertEqual(message.content, "Test message content")
        self.assertEqual(message.role, Message.Role.USER)

    def test_reuses_session_for_same_client(self):
        """Same client session should reuse the same ChatSession."""
        response1 = self.client.post("/chat/send/", {"message": "First"})
        session_id1 = json.loads(response1.content)["session_id"]

        response2 = self.client.post("/chat/send/", {"message": "Second"})
        session_id2 = json.loads(response2.content)["session_id"]

        self.assertEqual(session_id1, session_id2)
        self.assertEqual(ChatSession.objects.count(), 1)
        self.assertEqual(Message.objects.count(), 2)


class SendMessageAuthTests(TestCase):
    """Tests for authenticated user session handling."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    def test_authenticated_user_session_linked_to_user(self):
        """Authenticated user's session should be linked to their account."""
        self.client.login(username="testuser", password="testpass")

        self.client.post("/chat/send/", {"message": "Hello"})

        session = ChatSession.objects.first()
        self.assertEqual(session.user, self.user)


class StreamResponseOwnershipTests(TestCase):
    """Tests for session ownership verification in stream_response."""

    def setUp(self):
        self.client = Client()

    def test_404_for_nonexistent_session(self):
        """Non-existent session should return 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = self.client.get(f"/chat/stream/{fake_uuid}/")

        self.assertEqual(response.status_code, 404)

    def test_403_for_wrong_session_key(self):
        """Anonymous user cannot access another's session."""
        # Create session with different session key
        other_session = ChatSession.objects.create(
            session_key="other-session-key"
        )

        response = self.client.get(f"/chat/stream/{other_session.id}/")

        self.assertEqual(response.status_code, 403)

    def test_403_for_wrong_user(self):
        """Authenticated user cannot access another user's session."""
        other_user = User.objects.create_user(
            username="other", password="pass"
        )
        other_session = ChatSession.objects.create(user=other_user)

        User.objects.create_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

        response = self.client.get(f"/chat/stream/{other_session.id}/")

        self.assertEqual(response.status_code, 403)


class KeywordSearchTests(TestCase):
    """Tests for keyword search functionality."""

    def setUp(self):
        self.client = Client()

    def test_empty_query_returns_no_results(self):
        """Empty search should return empty results, not error."""
        Document.objects.create(
            title="Test Doc", content="content", category="test"
        )

        response = self.client.get("/chat/search/", {"q": ""})

        self.assertEqual(response.status_code, 200)
        # Template should render with empty results
        self.assertNotContains(response, "Test Doc")

    def test_category_filter_excludes_other_categories(self):
        """Category filter should exclude non-matching documents."""
        Document.objects.create(
            title="Family Doc", content="divorce info", category="family"
        )
        Document.objects.create(
            title="Tax Doc", content="divorce tax info", category="tax"
        )

        response = self.client.get(
            "/chat/search/", {"q": "divorce", "category": "family"}
        )

        self.assertContains(response, "Family Doc")
        self.assertNotContains(response, "Tax Doc")


@override_settings(CHAT_ENABLED=True, CHAT_PROVIDER="ollama")
class ChatStatusTests(TestCase):
    """Tests for chat status endpoint."""

    def setUp(self):
        self.client = Client()

    @patch("chat.views.chat_service")
    def test_returns_availability_status(self, mock_service):
        """Status endpoint should return current availability."""
        mock_service.is_available.return_value = True

        response = self.client.get("/chat/status/")

        data = json.loads(response.content)
        self.assertTrue(data["available"])
        self.assertTrue(data["enabled"])

    @override_settings(CHAT_ENABLED=False)
    def test_reflects_disabled_setting(self):
        """Status should reflect CHAT_ENABLED=False."""
        response = self.client.get("/chat/status/")

        data = json.loads(response.content)
        self.assertFalse(data["enabled"])
