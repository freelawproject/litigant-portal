"""
Tests for chat service layer - custom business logic.

Only tests custom code, not Django ORM basics.
"""

from unittest.mock import MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase

from chat.models import Document
from chat.services.search_service import KeywordSearchService

User = get_user_model()


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
