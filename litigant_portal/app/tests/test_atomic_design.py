"""
Tests for the Atomic Design summary page and the stage pages it frames.
"""

import re

import pytest
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from litigant_portal.app.views.pages import (
    ATOMIC_DESIGN_STAGES,
    ATOMIC_PLACEHOLDER_TOPICS,
    _sample_components,
)


class SampleComponentsTests(SimpleTestCase):
    """The "In the code" line is read from the sample template, so it
    can't drift from what the sample renders."""

    def test_follows_includes_and_lists_each_component_once_in_order(self):
        # atoms.html renders nothing itself; its atoms are in an include,
        # and icon and button appear there more than once.
        self.assertEqual(
            _sample_components("pages/atomic_design/atoms.html"),
            ["icon", "search-input", "button", "link"],
        )


@pytest.mark.postgres
class AtomicDesignStageTests(TestCase):
    def test_unknown_stage_is_404(self):
        response = self.client.get(
            reverse("pages:atomic_design_stage", args=["quarks"])
        )

        self.assertEqual(response.status_code, 404)

    def test_template_stage_is_the_home_template_with_placeholder_content(
        self,
    ):
        """Template and page share one template file; only the data differs."""
        response = self.client.get(
            reverse("pages:atomic_design_stage", args=["template"])
        )

        self.assertTemplateUsed(response, "pages/home.html")
        self.assertEqual(response.context["topics"], ATOMIC_PLACEHOLDER_TOPICS)
        self.assertTrue(response.context["court_name"])

    def test_framed_pages_allow_same_origin_framing(self):
        """The summary page frames every stage and the real home page; the
        default DENY would leave those frames blank."""
        urls = [
            reverse("pages:atomic_design_stage", args=[stage])
            for stage in ATOMIC_DESIGN_STAGES
        ]
        urls.append(reverse("pages:home"))

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["X-Frame-Options"], "SAMEORIGIN")


@pytest.mark.postgres
class AtomicDesignLevelSelectionTests(TestCase):
    """The level selector is plain links with a query string, so the view
    decides which level is shown and how its sample is framed."""

    def _get(self, **params):
        return self.client.get(reverse("pages:atomic_design"), params)

    def test_atoms_is_shown_by_default(self):
        response = self._get()

        self.assertEqual(response.context["current"]["stage"], "atoms")

    def test_unknown_level_falls_back_to_atoms(self):
        response = self._get(level="quarks")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current"]["stage"], "atoms")

    def test_exactly_one_level_is_current(self):
        response = self._get(level="organisms")

        current = [
            level["stage"]
            for level in response.context["levels"]
            if level["is_current"]
        ]
        self.assertEqual(current, ["organisms"])

    def test_stage_levels_frame_their_stage_page(self):
        response = self._get(level="molecules")

        self.assertEqual(
            response.context["current"]["frame_url"],
            reverse("pages:atomic_design_stage", args=["molecules"]),
        )

    def test_page_level_frames_the_real_home_page(self):
        response = self._get(level="page")

        self.assertEqual(
            response.context["current"]["frame_url"], reverse("pages:home")
        )

    def test_phone_view_applies_to_levels_wider_than_a_phone(self):
        organisms = self._get(level="organisms", viewport="phone")
        molecules = self._get(level="molecules", viewport="phone")

        self.assertTrue(organisms.context["current"]["phone"])
        self.assertFalse(molecules.context["current"]["phone"])

    def test_only_the_selected_level_card_is_marked_current(self):
        """The sidebar cards say which level is shown with aria-current, so
        the choice isn't carried by the coral tint alone. Molecules has no
        width choice, so its card is the only ?level= link marked current."""
        response = self._get(level="molecules")

        current_links = re.findall(
            r'<a href="(\?level=[^"]*)"[^>]*aria-current="page"',
            response.content.decode(),
        )
        self.assertEqual(current_links, ["?level=molecules"])

    def test_width_choice_renders_only_for_levels_with_a_phone_view(self):
        organisms = self._get(level="organisms").content.decode()
        molecules = self._get(level="molecules").content.decode()

        self.assertIn("?level=organisms&viewport=phone", organisms)
        self.assertNotIn("viewport=phone", molecules)


@pytest.mark.postgres
class InternalPageFrameTests(TestCase):
    def test_internal_pages_have_a_single_main_landmark(self):
        """Every internal page renders inside base.html's <main>; a second
        one inside it gives screen readers two main landmarks."""
        for name in (
            "pages:style_guide",
            "pages:atomic_design",
            "pages:a11y_guide",
        ):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))

                self.assertEqual(response.content.decode().count("<main"), 1)
