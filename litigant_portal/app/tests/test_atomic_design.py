"""
Tests for the Atomic Design summary page and the stage pages it frames.
"""

import pytest
from django.test import TestCase
from django.urls import reverse

from litigant_portal.app.views.pages import (
    ATOMIC_DESIGN_STAGES,
    ATOMIC_PLACEHOLDER_TOPICS,
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


@pytest.mark.postgres
class InternalPageFrameTests(TestCase):
    def test_internal_pages_have_a_single_main_landmark(self):
        """Both pages render inside base.html's <main>; a second one inside
        it gives screen readers two main landmarks."""
        for name in ("pages:style_guide", "pages:atomic_design"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))

                self.assertEqual(response.content.decode().count("<main"), 1)
