"""
Tests for the Accessibility (A11y) design-system page and the skip link it
explains.
"""

import pytest
from django.test import TestCase
from django.urls import reverse

from litigant_portal.app.theme import contrast_ratio, theme_colors


@pytest.mark.postgres
class A11yGuideSimulationTests(TestCase):
    """Simulations are plain ?simulate= links, so the view decides which
    one, if any, is applied to the demos."""

    def _get(self, **params):
        return self.client.get(reverse("pages:a11y_guide"), params)

    def test_no_simulation_by_default(self):
        response = self._get()

        self.assertIsNone(response.context["simulation"])

    def test_a_known_simulation_is_applied(self):
        response = self._get(simulate="deuteranopia")

        self.assertEqual(response.context["simulation"]["key"], "deuteranopia")

    def test_an_unknown_simulation_is_ignored(self):
        response = self._get(simulate="x-ray")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["simulation"])


@pytest.mark.postgres
class A11yGuideContrastTests(TestCase):
    def test_contrast_samples_are_measured_from_the_theme(self):
        """The ratios on the page come from src/main.css, so they stay true
        when the palette changes."""
        response = self.client.get(reverse("pages:a11y_guide"))
        colors = theme_colors()

        for sample in response.context["contrast_samples"]:
            with self.subTest(sample=sample["foreground"]):
                self.assertEqual(
                    sample["ratio"],
                    contrast_ratio(
                        colors[sample["foreground"]],
                        colors[sample["background"]],
                    ),
                )

    def test_samples_span_pass_borderline_and_fail(self):
        response = self.client.get(reverse("pages:a11y_guide"))

        levels = [s["level"] for s in response.context["contrast_samples"]]
        self.assertEqual(levels, ["AAA", "AA", "Fail"])


@pytest.mark.postgres
class SkipLinkTests(TestCase):
    def test_skip_link_targets_the_main_landmark(self):
        """WCAG 2.4.1: the first focusable element jumps past the header to
        <main>, so the link and its target must both be on every page."""
        content = self.client.get(reverse("pages:home")).content.decode()

        self.assertIn('href="#main-content"', content)
        self.assertIn('<main id="main-content"', content)
