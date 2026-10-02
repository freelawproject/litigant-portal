"""
Tests for the skip link on every page.
"""

import pytest
from django.test import TestCase
from django.urls import reverse


@pytest.mark.postgres
class SkipLinkTests(TestCase):
    def test_skip_link_targets_the_main_landmark(self):
        """WCAG 2.4.1: the first focusable element jumps past the header to
        <main>, so the link and its target must both be on every page."""
        content = self.client.get(reverse("pages:home")).content.decode()

        self.assertIn('href="#main-content"', content)
        self.assertIn('<main id="main-content"', content)
