"""
Tests for chat service layer - custom business logic.

Only tests custom code, not Django ORM basics.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings

from chat.models import ChatSession, Document, Message
from chat.services.chat_service import ChatService
from chat.services.search_service import KeywordSearchService

User = get_user_model()


class ChatServiceSessionManagementTests(TestCase):
    """Tests for session creation and retrieval logic."""

    def setUp(self):
        self.service = ChatService()
        self.factory = RequestFactory()

    def test_creates_new_session_for_authenticated_user(self):
        """First request from auth user creates a new session."""
        user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        request = self.factory.post("/chat/send/")
        request.user = user

        session = self.service.get_or_create_session(request)

        self.assertEqual(session.user, user)
        self.assertEqual(ChatSession.objects.count(), 1)

    def test_reuses_existing_session_for_same_user(self):
        """Subsequent requests reuse the existing session."""
        user = User.objects.create_user(
            username="testuser", password="testpass"
        )
        existing = ChatSession.objects.create(user=user)

        request = self.factory.post("/chat/send/")
        request.user = user

        session = self.service.get_or_create_session(request)

        self.assertEqual(session.id, existing.id)
        self.assertEqual(ChatSession.objects.count(), 1)

    def test_anonymous_user_gets_session_by_session_key(self):
        """Anonymous users are tracked by Django session key."""
        request = self.factory.post("/chat/send/")
        request.user = MagicMock(is_authenticated=False)
        request.session = MagicMock()
        request.session.session_key = "test-session-key"

        session = self.service.get_or_create_session(request)

        self.assertIsNone(session.user)
        self.assertEqual(session.session_key, "test-session-key")

    def test_creates_django_session_if_missing(self):
        """Should create Django session for anonymous user if none exists."""
        request = self.factory.post("/chat/send/")
        request.user = MagicMock(is_authenticated=False)
        request.session = MagicMock()
        request.session.session_key = None

        def set_key():
            request.session.session_key = "new-key"

        request.session.create.side_effect = set_key

        self.service.get_or_create_session(request)

        request.session.create.assert_called_once()

    def test_get_session_returns_none_for_invalid_id(self):
        """get_session returns None, not exception, for missing session."""
        result = self.service.get_session(
            "00000000-0000-0000-0000-000000000000"
        )

        self.assertIsNone(result)


class ChatServiceMessageTests(TestCase):
    """Tests for message creation logic."""

    def setUp(self):
        self.service = ChatService()
        self.session = ChatSession.objects.create()

    def test_add_user_message_sets_user_role(self):
        """Messages created via add_user_message have USER role."""
        message = self.service.add_user_message(self.session, "Hello")

        self.assertEqual(message.role, Message.Role.USER)


class ChatServiceMessageHistoryTests(TestCase):
    """Tests for message history building."""

    def setUp(self):
        self.service = ChatService()
        self.session = ChatSession.objects.create()

    def test_build_message_history_orders_chronologically(self):
        """Messages should be in order they were created."""
        Message.objects.create(
            session=self.session, role=Message.Role.USER, content="First"
        )
        Message.objects.create(
            session=self.session,
            role=Message.Role.ASSISTANT,
            content="Second",
        )
        Message.objects.create(
            session=self.session, role=Message.Role.USER, content="Third"
        )

        history = self.service.build_message_history(self.session)

        self.assertEqual(history[0].content, "First")
        self.assertEqual(history[1].content, "Second")
        self.assertEqual(history[2].content, "Third")

    def test_build_message_history_includes_role(self):
        """Each history item should have the correct role."""
        Message.objects.create(
            session=self.session, role=Message.Role.USER, content="Question"
        )
        Message.objects.create(
            session=self.session,
            role=Message.Role.ASSISTANT,
            content="Answer",
        )

        history = self.service.build_message_history(self.session)

        self.assertEqual(history[0].role, "user")
        self.assertEqual(history[1].role, "assistant")


class ChatServiceStreamResponseTests(TestCase):
    """Tests for stream_response error handling and message saving."""

    def setUp(self):
        self.service = ChatService()
        self.session = ChatSession.objects.create()
        # Add a user message so there's something to respond to
        Message.objects.create(
            session=self.session, role=Message.Role.USER, content="Hello"
        )

    @patch("chat.services.chat_service.get_provider")
    def test_saves_assistant_message_on_success(self, mock_get_provider):
        """Successful stream should save the complete response."""
        mock_provider = MagicMock()
        mock_provider.stream_response.return_value = iter(["Hello", " world"])
        mock_get_provider.return_value = mock_provider

        response = self.service.stream_response(self.session)
        # Consume the generator to trigger message saving
        list(response.streaming_content)

        assistant_msg = Message.objects.filter(
            session=self.session, role=Message.Role.ASSISTANT
        ).first()
        self.assertIsNotNone(assistant_msg)
        self.assertEqual(assistant_msg.content, "Hello world")

    @patch("chat.services.chat_service.get_provider")
    def test_saves_error_message_on_provider_failure(self, mock_get_provider):
        """Provider failure should save an error message."""
        mock_get_provider.side_effect = Exception("Connection refused")

        response = self.service.stream_response(self.session)
        # Consume the generator to trigger error handling
        list(response.streaming_content)

        assistant_msg = Message.objects.filter(
            session=self.session, role=Message.Role.ASSISTANT
        ).first()
        self.assertIsNotNone(assistant_msg)
        self.assertIn("error", assistant_msg.content.lower())

    @patch("chat.services.chat_service.get_provider")
    def test_streams_done_signal_on_completion(self, mock_get_provider):
        """Stream should end with [DONE] signal."""
        mock_provider = MagicMock()
        mock_provider.stream_response.return_value = iter(["Hi"])
        mock_get_provider.return_value = mock_provider

        response = self.service.stream_response(self.session)
        content = list(response.streaming_content)

        # Last event should be [DONE]
        self.assertTrue(any(b"[DONE]" in chunk for chunk in content))


class ChatServiceAvailabilityTests(TestCase):
    """Tests for service availability checks."""

    def setUp(self):
        self.service = ChatService()

    @override_settings(CHAT_ENABLED=False)
    def test_unavailable_when_disabled(self):
        """is_available returns False when CHAT_ENABLED=False."""
        result = self.service.is_available()

        self.assertFalse(result)

    @override_settings(CHAT_ENABLED=True)
    @patch("chat.services.chat_service.get_provider")
    def test_checks_provider_health(self, mock_get_provider):
        """is_available checks provider health when enabled."""
        mock_provider = MagicMock()
        mock_provider.health_check.return_value = True
        mock_get_provider.return_value = mock_provider

        result = self.service.is_available()

        self.assertTrue(result)
        mock_provider.health_check.assert_called_once()

    @override_settings(CHAT_ENABLED=True)
    @patch("chat.services.chat_service.get_provider")
    def test_unavailable_when_provider_fails(self, mock_get_provider):
        """is_available returns False if provider health check fails."""
        mock_get_provider.side_effect = Exception("Connection refused")

        result = self.service.is_available()

        self.assertFalse(result)


class KeywordSearchTests(TestCase):
    """Tests for keyword search service logic."""

    def setUp(self):
        self.service = KeywordSearchService()

    def test_empty_query_returns_empty(self):
        """Empty/whitespace queries should return no results."""
        Document.objects.create(
            title="Test", content="Content", category="test"
        )

        results = list(self.service.search(""))
        results_whitespace = list(self.service.search("   "))

        self.assertEqual(results, [])
        self.assertEqual(results_whitespace, [])

    def test_category_filter_works(self):
        """Category parameter should filter results."""
        Document.objects.create(
            title="Doc 1", content="legal info", category="family"
        )
        Document.objects.create(
            title="Doc 2", content="legal info", category="tax"
        )

        results = list(self.service.search("legal", category="family"))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].category, "family")

    def test_limit_parameter_works(self):
        """Limit should cap the number of results."""
        for i in range(10):
            Document.objects.create(
                title=f"Doc {i}", content="test content", category="test"
            )

        results = list(self.service.search("test", limit=3))

        self.assertEqual(len(results), 3)


class KeywordSearchCategoriesTests(TestCase):
    """Tests for category listing."""

    def setUp(self):
        self.service = KeywordSearchService()

    def test_get_categories_returns_unique_values(self):
        """Should return unique categories, not duplicates."""
        Document.objects.create(title="A", content="c", category="family")
        Document.objects.create(title="B", content="c", category="family")
        Document.objects.create(title="C", content="c", category="tax")

        categories = self.service.get_categories()

        self.assertEqual(len(categories), 2)
        self.assertIn("family", categories)
        self.assertIn("tax", categories)

    def test_get_categories_sorted_alphabetically(self):
        """Categories should be in alphabetical order."""
        Document.objects.create(title="A", content="c", category="tax")
        Document.objects.create(title="B", content="c", category="criminal")
        Document.objects.create(title="C", content="c", category="family")

        categories = self.service.get_categories()

        self.assertEqual(categories, ["criminal", "family", "tax"])
