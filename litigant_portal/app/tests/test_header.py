"""
Tests for the site brand (c-molecules.logo) and the court props the shared
header takes from the page context.
"""

import pytest
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse
from django_cotton.utils import render_component

COURT_NAME = "State of North Dakota Courts"
COURT_LOGO = "/static/images/court-logo.png"
COURT_NAME_IMAGE = "/static/images/court-name.png"
FLP_LOGO = "images/logo_powered.svg"


def _render_logo(**props):
    return render_component(RequestFactory().get("/"), "molecules.logo", props)


class LogoTests(SimpleTestCase):
    def test_court_name_switches_to_the_court_variant(self):
        html = _render_logo(court_name=COURT_NAME, court_logo=COURT_LOGO)

        self.assertIn(COURT_NAME, html)
        self.assertNotIn(FLP_LOGO, html)

    def test_without_a_court_the_flp_logo_stands_alone(self):
        html = _render_logo()

        self.assertIn(FLP_LOGO, html)

    def test_court_name_image_is_named_by_the_court_name(self):
        """The name art must carry the court name as its alt text, or the
        link's accessible name loses the court (WCAG 1.1.1, 2.5.3)."""
        html = _render_logo(
            court_name=COURT_NAME,
            court_logo=COURT_LOGO,
            court_name_image=COURT_NAME_IMAGE,
        )

        self.assertIn(f'src="{COURT_NAME_IMAGE}" alt="{COURT_NAME}"', html)

    def test_court_logo_is_decorative(self):
        """The court name already names the link; an alt on the seal would
        make screen readers announce the court twice."""
        html = _render_logo(court_name=COURT_NAME, court_logo=COURT_LOGO)

        self.assertIn(f'src="{COURT_LOGO}" alt=""', html)

    def test_collapse_needs_a_court_logo_to_fall_back_on(self):
        """Collapsing hides the name; with no logo that would leave nothing
        visible, so the responsive frame is only switched on with one."""
        with_logo = _render_logo(court_name=COURT_NAME, court_logo=COURT_LOGO)
        name_only = _render_logo(court_name=COURT_NAME)

        self.assertIn("logo-frame-responsive", with_logo)
        self.assertNotIn("logo-frame-responsive", name_only)


@pytest.mark.postgres
class HeaderCourtContextTests(TestCase):
    def test_header_without_court_context_shows_the_flp_logo(self):
        response = self.client.get(reverse("pages:home"))

        self.assertIn(FLP_LOGO, response.content.decode())
