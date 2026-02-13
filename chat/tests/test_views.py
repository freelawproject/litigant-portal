"""
Tests for chat views - custom validation and business logic.

Only tests custom code, not Django built-ins like @require_POST.
"""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from chat.agents import agent_registry
from chat.agents.base import Agent
from chat.models import ChatSession, Document, Message

User = get_user_model()


class MockAgent(Agent):
    """Mock agent for testing."""

    default_model = "mock/model"
    default_messages = [{"role": "system", "content": "Test assistant."}]

    def ping(self) -> bool:
        return True

    def stream_run(self, messages=None, **kwargs):
        # Add user message if provided
        if messages is not None:
            if isinstance(messages, str):
                self.add_message({"role": "user", "content": messages})
            else:
                for msg in messages:
                    self.add_message(msg)

        # Add assistant response
        self.add_message({"role": "assistant", "content": "Hello world"})

        yield {"type": "content_delta", "content": "Hello"}
        yield {"type": "content_delta", "content": " world"}
        yield {"type": "done"}


# Register mock agent
agent_registry["MockAgent"] = MockAgent


@override_settings(DEFAULT_CHAT_AGENT="MockAgent")
class StreamValidationTests(TestCase):
    """Tests for message validation in stream endpoint."""

    def setUp(self):
        self.client = Client()

    def test_rejects_empty_message(self):
        """Empty messages should be rejected with 400."""
        response = self.client.post("/api/chat/stream/", {"message": ""})

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("error", data)

    def test_rejects_whitespace_only_message(self):
        """Whitespace-only messages should be rejected."""
        response = self.client.post("/api/chat/stream/", {"message": "   "})

        self.assertEqual(response.status_code, 400)

    def test_rejects_message_over_2000_chars(self):
        """Messages over 2000 characters should be rejected."""
        long_message = "x" * 2001
        response = self.client.post(
            "/api/chat/stream/", {"message": long_message}
        )

        self.assertEqual(response.status_code, 400)
        data = json.loads(response.content)
        self.assertIn("2000", data["error"])

    def test_accepts_message_at_2000_chars(self):
        """Messages exactly 2000 characters should be accepted."""
        max_message = "x" * 2000
        response = self.client.post(
            "/api/chat/stream/", {"message": max_message}
        )

        # Should return streaming response, not error
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/event-stream")


@override_settings(DEFAULT_CHAT_AGENT="MockAgent")
class StreamSessionTests(TestCase):
    """Tests for session management in stream endpoint."""

    def setUp(self):
        self.client = Client()

    def test_returns_session_id_in_stream(self):
        """Stream should include session event with session_id."""
        response = self.client.post("/api/chat/stream/", {"message": "Hello"})

        content = b"".join(response.streaming_content).decode()
        self.assertIn('"type": "session"', content)
        self.assertIn('"session_id"', content)

    def test_creates_message_with_user_content(self):
        """The message content should be saved to the database."""
        response = self.client.post(
            "/api/chat/stream/", {"message": "Test message content"}
        )
        # Consume the stream
        list(response.streaming_content)

        # Find the user message (first message is system prompt)
        message = Message.objects.filter(data__role="user").first()
        self.assertEqual(message.content, "Test message content")
        self.assertEqual(message.role, "user")

    def test_reuses_session_when_session_id_provided(self):
        """Providing session_id reuses that session."""
        # First request creates session
        response1 = self.client.post("/api/chat/stream/", {"message": "First"})
        content1 = b"".join(response1.streaming_content).decode()

        # Extract session_id from stream
        import re

        match = re.search(r'"session_id":\s*"([^"]+)"', content1)
        session_id = match.group(1)

        # Second request with session_id
        response2 = self.client.post(
            "/api/chat/stream/",
            {"message": "Second", "session_id": session_id},
        )
        list(response2.streaming_content)

        # Should have: 1 system message + 2 user messages + 2 assistant messages
        user_messages = Message.objects.filter(data__role="user").count()
        self.assertEqual(user_messages, 2)
        self.assertEqual(ChatSession.objects.count(), 1)


@override_settings(DEFAULT_CHAT_AGENT="MockAgent")
class StreamAuthTests(TestCase):
    """Tests for authenticated user session handling."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    def test_authenticated_user_session_linked_to_user(self):
        """Authenticated user's session should be linked to their account."""
        self.client.login(username="testuser", password="testpass")

        response = self.client.post("/api/chat/stream/", {"message": "Hello"})
        list(response.streaming_content)

        session = ChatSession.objects.first()
        self.assertEqual(session.user, self.user)


@override_settings(DEFAULT_CHAT_AGENT="MockAgent")
class StreamOwnershipTests(TestCase):
    """Tests for session ownership verification."""

    def setUp(self):
        self.client = Client()

    def test_404_for_nonexistent_session(self):
        """Non-existent session should return 404."""
        fake_uuid = "00000000-0000-0000-0000-000000000000"
        response = self.client.post(
            "/api/chat/stream/", {"message": "Hello", "session_id": fake_uuid}
        )

        self.assertEqual(response.status_code, 404)

    def test_403_for_wrong_session_key(self):
        """Anonymous user cannot access another's session."""
        # Create session with different session key
        other_session = ChatSession.objects.create(
            session_key="other-session-key"
        )

        response = self.client.post(
            "/api/chat/stream/",
            {"message": "Hello", "session_id": str(other_session.id)},
        )

        self.assertEqual(response.status_code, 403)

    def test_403_for_wrong_user(self):
        """Authenticated user cannot access another user's session."""
        other_user = User.objects.create_user(
            username="other", password="pass"
        )
        other_session = ChatSession.objects.create(user=other_user)

        User.objects.create_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

        response = self.client.post(
            "/api/chat/stream/",
            {"message": "Hello", "session_id": str(other_session.id)},
        )

        self.assertEqual(response.status_code, 403)


class SearchTests(TestCase):
    """Tests for keyword search functionality."""

    def setUp(self):
        self.client = Client()

    def test_empty_query_returns_no_results(self):
        """Empty search should return empty results, not error."""
        Document.objects.create(
            title="Test Doc", content="content", category="test"
        )

        response = self.client.get("/api/chat/search/", {"q": ""})

        self.assertEqual(response.status_code, 200)
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
            "/api/chat/search/", {"q": "divorce", "category": "family"}
        )

        self.assertContains(response, "Family Doc")
        self.assertNotContains(response, "Tax Doc")


@override_settings(CHAT_ENABLED=True, DEFAULT_CHAT_AGENT="MockAgent")
class StatusTests(TestCase):
    """Tests for chat status endpoint."""

    def setUp(self):
        self.client = Client()

    def test_returns_availability_status(self):
        """Status endpoint should return current availability."""
        response = self.client.get("/api/chat/status/")

        data = json.loads(response.content)
        self.assertTrue(data["available"])
        self.assertTrue(data["enabled"])

    @override_settings(CHAT_ENABLED=False)
    def test_reflects_disabled_setting(self):
        """Status should reflect CHAT_ENABLED=False."""
        response = self.client.get("/api/chat/status/")

        data = json.loads(response.content)
        self.assertFalse(data["enabled"])
