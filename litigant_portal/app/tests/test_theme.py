"""
Tests for reading theme colours from src/main.css and computing WCAG
contrast ratios between them.
"""

from django.test import SimpleTestCase

from litigant_portal.app.theme import (
    contrast_level,
    contrast_ratio,
    theme_colors,
)


class ContrastRatioTests(SimpleTestCase):
    def test_black_on_white_is_the_maximum(self):
        self.assertEqual(contrast_ratio("#000000", "#ffffff"), 21.0)

    def test_a_colour_against_itself_is_the_minimum(self):
        self.assertEqual(contrast_ratio("#776f61", "#776f61"), 1.0)

    def test_order_does_not_matter(self):
        self.assertEqual(
            contrast_ratio("#ffffff", "#1c1814"),
            contrast_ratio("#1c1814", "#ffffff"),
        )

    def test_mid_grey_matches_the_published_wcag_value(self):
        """#767676 is the lightest grey that passes 4.5:1 on white, a value
        WebAIM's checker and most references cite."""
        self.assertEqual(contrast_ratio("#767676", "#ffffff"), 4.54)

    def test_shorthand_hex_is_expanded(self):
        self.assertEqual(contrast_ratio("#000", "#fff"), 21.0)


class ThemeColorsTests(SimpleTestCase):
    def test_reads_colour_tokens_from_the_theme(self):
        colors = theme_colors()

        self.assertRegex(colors["greyscale-900"], r"^#[0-9a-f]{6}$")
        self.assertIn("primary-600", colors)

    def test_white_and_black_are_always_available(self):
        """Tailwind ships white and black without a theme token, and most
        pairs on the page are measured against white."""
        colors = theme_colors()

        self.assertEqual(colors["white"], "#ffffff")
        self.assertEqual(colors["black"], "#000000")


class ContrastLevelTests(SimpleTestCase):
    """WCAG 2.2 text thresholds: 7:1 for AAA (1.4.6), 4.5:1 for AA (1.4.3),
    and 3:1, which AA allows only for large text."""

    def test_thresholds_are_inclusive(self):
        self.assertEqual(contrast_level(7.0), "AAA")
        self.assertEqual(contrast_level(4.5), "AA")
        self.assertEqual(contrast_level(3.0), "AA large text")

    def test_just_below_a_threshold_drops_a_level(self):
        self.assertEqual(contrast_level(6.99), "AA")
        self.assertEqual(contrast_level(4.49), "AA large text")
        self.assertEqual(contrast_level(2.99), "Fail")
