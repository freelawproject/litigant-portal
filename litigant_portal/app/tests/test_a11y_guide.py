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
    """The switcher is radios that CSS watches, so the server's only job is
    to pre-check one from ?simulate=, for links that open the page with a
    simulation on."""

    def _get(self, **params):
        return self.client.get(reverse("pages:a11y_guide"), params)

    def _checked_keys(self, response):
        return [
            option["key"]
            for group in response.context["simulation_groups"]
            for option in group["options"]
            if option["checked"]
        ]

    def test_typical_vision_is_checked_by_default(self):
        response = self._get()

        self.assertEqual(self._checked_keys(response), [""])

    def test_simulate_checks_the_matching_radio(self):
        response = self._get(simulate="deuteranopia")

        self.assertEqual(self._checked_keys(response), ["deuteranopia"])

    def test_an_unknown_simulation_falls_back_to_typical_vision(self):
        response = self._get(simulate="x-ray")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._checked_keys(response), [""])

    def test_radio_ids_are_unique(self):
        """main.css finds each radio by id (#sim-<key>), and typical vision
        has the empty key, so it needs an id of its own."""
        response = self._get()

        ids = [
            option["input_id"]
            for group in response.context["simulation_groups"]
            for option in group["options"]
        ]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("sim-typical", ids)
        self.assertIn("sim-cataracts", ids)

    def test_try_it_links_open_the_simulation_at_their_section(self):
        response = self._get()

        hrefs = {
            section: link["href"]
            for section, link in response.context["try_it"].items()
        }
        self.assertEqual(
            hrefs,
            {
                "contrast": "?simulate=cataracts#contrast",
                "colour_alone": "?simulate=deuteranopia#colour-alone",
            },
        )


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

    def test_a_sample_passes_only_at_body_text_contrast(self):
        """The samples are body text, so the pass/fail label follows the
        4.5:1 AA threshold, not the 3:1 one for large text."""
        response = self.client.get(reverse("pages:a11y_guide"))

        verdicts = [s["passes"] for s in response.context["contrast_samples"]]
        self.assertEqual(verdicts, [True, True, False])


@pytest.mark.postgres
class SkipLinkTests(TestCase):
    def test_skip_link_targets_the_main_landmark(self):
        """WCAG 2.4.1: the first focusable element jumps past the header to
        <main>, so the link and its target must both be on every page."""
        content = self.client.get(reverse("pages:home")).content.decode()

        self.assertIn('href="#main-content"', content)
        self.assertIn('<main id="main-content"', content)
