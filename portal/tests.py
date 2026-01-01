"""
Smoke tests for the Litigant Portal.

YAGNI approach: Only test what exists and matters.
- Views respond with 200
- Templates render without errors
- Django system checks pass

Skip for now (no implementation yet):
- Model tests
- Selenium/browser tests
- API tests
"""

from django.core.management import call_command
from django.test import TestCase


class ViewSmokeTests(TestCase):
    """Verify all views respond and templates render correctly."""

    def test_home_page(self):
        """Home page loads successfully."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/home.html")

    def test_style_guide_page(self):
        """Style guide page loads successfully."""
        response = self.client.get("/style-guide/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/style_guide.html")


class DjangoSystemTests(TestCase):
    """Verify Django configuration is correct."""

    def test_system_checks_pass(self):
        """Django system checks should pass without warnings."""
        # This catches misconfigurations early
        call_command("check", "--fail-level", "WARNING")
