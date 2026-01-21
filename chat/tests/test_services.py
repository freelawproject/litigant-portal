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


class PDFServiceValidationTests(TestCase):
    """Tests for PDF upload validation logic."""

    def setUp(self):
        from chat.services.pdf_service import PDFService

        self.service = PDFService()

    def _make_mock_file(
        self, name="test.pdf", content_type="application/pdf", size=1024
    ):
        """Create a mock uploaded file."""
        mock_file = MagicMock()
        mock_file.name = name
        mock_file.content_type = content_type
        mock_file.size = size
        return mock_file

    def test_valid_pdf_passes_validation(self):
        """Valid PDF file should pass all validation checks."""
        mock_file = self._make_mock_file()

        is_valid, error = self.service.validate_upload(mock_file)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_rejects_non_pdf_content_type(self):
        """Non-PDF content types should be rejected."""
        mock_file = self._make_mock_file(content_type="image/png")

        is_valid, error = self.service.validate_upload(mock_file)

        self.assertFalse(is_valid)
        self.assertIn("PDF", error)

    def test_rejects_oversized_file(self):
        """Files over 10MB should be rejected."""
        mock_file = self._make_mock_file(size=11 * 1024 * 1024)

        is_valid, error = self.service.validate_upload(mock_file)

        self.assertFalse(is_valid)
        self.assertIn("10MB", error)

    def test_rejects_wrong_extension(self):
        """Files without .pdf extension should be rejected."""
        mock_file = self._make_mock_file(name="document.docx")

        is_valid, error = self.service.validate_upload(mock_file)

        self.assertFalse(is_valid)
        self.assertIn(".pdf", error)

    def test_accepts_uppercase_extension(self):
        """Uppercase .PDF extension should be accepted."""
        mock_file = self._make_mock_file(name="DOCUMENT.PDF")

        is_valid, error = self.service.validate_upload(mock_file)

        self.assertTrue(is_valid)
        self.assertIsNone(error)


class ExtractionServiceInputTests(TestCase):
    """Tests for extraction service input handling."""

    def setUp(self):
        from chat.services.extraction_service import ExtractionService

        self.service = ExtractionService()

    def test_empty_text_returns_error(self):
        """Empty document text should return error result."""
        result = self.service.extract_from_text("")

        self.assertFalse(result.success)
        self.assertIn("No document text", result.error)

    def test_whitespace_only_returns_error(self):
        """Whitespace-only text should return error result."""
        result = self.service.extract_from_text("   \n\t  ")

        self.assertFalse(result.success)
        self.assertIn("No document text", result.error)

    @patch("chat.services.extraction_service.get_provider")
    def test_provider_exception_returns_error(self, mock_get_provider):
        """Provider failure should return error result, not raise."""
        mock_get_provider.side_effect = Exception("API error")

        result = self.service.extract_from_text("Some document text")

        self.assertFalse(result.success)
        self.assertIn("Failed to analyze", result.error)


class ExtractionServiceParsingTests(TestCase):
    """Tests for extraction result parsing logic."""

    def setUp(self):
        from chat.services.extraction_service import ExtractionService

        self.service = ExtractionService()

    def test_parses_complete_result(self):
        """Should correctly parse a complete LLM response."""
        raw_result = {
            "case_type": "Eviction",
            "court_info": {
                "county": "Bexar County",
                "court_name": "Justice Court Precinct 1",
                "case_number": "2024-CV-12345",
            },
            "parties": {
                "user_name": "Jane Doe",
                "opposing_party": "ABC Properties LLC",
            },
            "key_dates": [
                {
                    "label": "Court hearing",
                    "date": "2024-02-15",
                    "is_deadline": True,
                },
                {
                    "label": "Filing date",
                    "date": "2024-01-10",
                    "is_deadline": False,
                },
            ],
            "summary": "This is an eviction notice.",
            "confidence": 0.85,
        }

        result = self.service._parse_extraction_result(raw_result)

        self.assertTrue(result.success)
        self.assertEqual(result.case_type, "Eviction")
        self.assertEqual(result.court_info.county, "Bexar County")
        self.assertEqual(result.court_info.case_number, "2024-CV-12345")
        self.assertEqual(result.parties.user_name, "Jane Doe")
        self.assertEqual(result.parties.opposing_party, "ABC Properties LLC")
        self.assertEqual(len(result.key_dates), 2)
        self.assertTrue(result.key_dates[0].is_deadline)
        self.assertEqual(result.confidence, 0.85)

    def test_handles_missing_optional_fields(self):
        """Should handle missing optional fields gracefully."""
        raw_result = {
            "case_type": "Small Claims",
            "summary": "A small claims case.",
            "confidence": 0.5,
        }

        result = self.service._parse_extraction_result(raw_result)

        self.assertTrue(result.success)
        self.assertEqual(result.case_type, "Small Claims")
        self.assertIsNone(result.court_info.county)
        self.assertIsNone(result.parties.user_name)
        self.assertEqual(result.key_dates, [])

    def test_handles_empty_result(self):
        """Should handle empty result dict without error."""
        result = self.service._parse_extraction_result({})

        self.assertTrue(result.success)
        self.assertEqual(result.case_type, "")
        self.assertEqual(result.confidence, 0.0)


class ExtractionResultSerializationTests(TestCase):
    """Tests for ExtractionResult.to_dict() method."""

    def test_to_dict_serializes_all_fields(self):
        """to_dict should produce JSON-serializable output."""
        from chat.services.extraction_service import (
            CourtInfo,
            ExtractionResult,
            KeyDate,
            Parties,
        )

        result = ExtractionResult(
            success=True,
            case_type="Eviction",
            court_info=CourtInfo(
                county="Travis", court_name="JP Court", case_number="123"
            ),
            parties=Parties(user_name="John", opposing_party="Landlord Inc"),
            key_dates=[
                KeyDate(label="Hearing", date="2024-03-01", is_deadline=True)
            ],
            summary="Test summary",
            confidence=0.9,
        )

        output = result.to_dict()

        self.assertEqual(output["success"], True)
        self.assertEqual(output["case_type"], "Eviction")
        self.assertEqual(output["court_info"]["county"], "Travis")
        self.assertEqual(output["parties"]["user_name"], "John")
        self.assertEqual(len(output["key_dates"]), 1)
        self.assertEqual(output["key_dates"][0]["is_deadline"], True)

    def test_to_dict_handles_none_values(self):
        """to_dict should handle None values correctly."""
        from chat.services.extraction_service import ExtractionResult

        result = ExtractionResult(success=False, error="Test error")

        output = result.to_dict()

        self.assertEqual(output["success"], False)
        self.assertEqual(output["error"], "Test error")
        self.assertIsNone(output["court_info"]["county"])
