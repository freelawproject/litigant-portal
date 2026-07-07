"""Tests for the demo court context switcher (#632).

Helper + context-processor tests are DB-free (SimpleTestCase). The view and
chat_page tests exercise the session end-to-end via the test client.
"""

import pytest
from django.test import (
    RequestFactory,
    SimpleTestCase,
    TestCase,
    override_settings,
)
from django.urls import reverse

from litigant_portal.app import court_context as cc
from litigant_portal.app.context_processors import court_context


class CourtContextHelperTests(SimpleTestCase):
    """The single validated path for reading/writing the active court."""

    def setUp(self):
        self.factory = RequestFactory()

    def _req(self, session=None):
        request = self.factory.get("/")
        request.session = {} if session is None else session
        return request

    @override_settings(DEPLOYMENT_ENV="dev")
    def test_switcher_enabled_in_dev(self):
        self.assertTrue(cc.switcher_enabled())

    @override_settings(DEPLOYMENT_ENV="qa")
    def test_switcher_enabled_in_qa(self):
        self.assertTrue(cc.switcher_enabled())

    @override_settings(DEPLOYMENT_ENV="prod")
    def test_switcher_disabled_in_prod(self):
        self.assertFalse(cc.switcher_enabled())

    def test_active_court_empty_when_unset(self):
        self.assertEqual(cc.get_active_court(self._req()), "")

    def test_active_court_returns_known_slug(self):
        request = self._req({cc.SESSION_KEY: "north-dakota"})
        self.assertEqual(cc.get_active_court(request), "north-dakota")

    def test_active_court_rejects_unknown_slug(self):
        # A stale/tampered session value must not leak an unknown court.
        request = self._req({cc.SESSION_KEY: "atlantis"})
        self.assertEqual(cc.get_active_court(request), "")

    def test_set_stores_known_court(self):
        request = self._req()
        self.assertEqual(
            cc.set_active_court(request, "north-dakota"), "north-dakota"
        )
        self.assertEqual(request.session[cc.SESSION_KEY], "north-dakota")

    def test_set_blank_clears_selection(self):
        request = self._req({cc.SESSION_KEY: "north-dakota"})
        self.assertEqual(cc.set_active_court(request, ""), "")
        self.assertNotIn(cc.SESSION_KEY, request.session)

    def test_set_unknown_clears_selection(self):
        request = self._req({cc.SESSION_KEY: "north-dakota"})
        self.assertEqual(cc.set_active_court(request, "atlantis"), "")
        self.assertNotIn(cc.SESSION_KEY, request.session)

    def test_set_normalizes_case_and_whitespace(self):
        request = self._req()
        self.assertEqual(
            cc.set_active_court(request, "  North-Dakota "), "north-dakota"
        )

    def test_available_courts_shape_includes_known_court(self):
        courts = cc.available_courts()
        self.assertTrue(all({"slug", "name"} <= set(c) for c in courts))
        self.assertIn("north-dakota", [c["slug"] for c in courts])


class CourtContextProcessorTests(SimpleTestCase):
    """Exposes the switcher + active court to every template."""

    def setUp(self):
        self.factory = RequestFactory()

    def _req(self, session=None):
        request = self.factory.get("/")
        request.session = {} if session is None else session
        return request

    @override_settings(DEPLOYMENT_ENV="dev")
    def test_exposes_switcher_and_courts(self):
        ctx = court_context(self._req())
        self.assertTrue(ctx["court_switcher_enabled"])
        self.assertIn(
            "north-dakota", [c["slug"] for c in ctx["available_courts"]]
        )
        self.assertEqual(ctx["active_court"], "")
        self.assertEqual(ctx["active_court_name"], "")

    @override_settings(DEPLOYMENT_ENV="prod")
    def test_switcher_disabled_in_prod(self):
        self.assertFalse(court_context(self._req())["court_switcher_enabled"])

    def test_reflects_active_court_from_session(self):
        ctx = court_context(self._req({cc.SESSION_KEY: "north-dakota"}))
        self.assertEqual(ctx["active_court"], "north-dakota")
        self.assertTrue(ctx["active_court_name"])  # resolved display name


@pytest.mark.postgres
class SetCourtViewTests(TestCase):
    """POST-only view that writes the session and redirects safely."""

    def test_post_sets_court_and_redirects_to_next(self):
        resp = self.client.post(
            reverse("pages:set_court"),
            {
                "court": "north-dakota",
                "next": "/chat/?topic=adult_name_change",
            },
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, "/chat/?topic=adult_name_change")
        self.assertEqual(self.client.session[cc.SESSION_KEY], "north-dakota")

    def test_post_blank_clears_selection(self):
        self.client.post(reverse("pages:set_court"), {"court": "north-dakota"})
        self.client.post(reverse("pages:set_court"), {"court": ""})
        self.assertNotIn(cc.SESSION_KEY, self.client.session)

    def test_offsite_next_falls_back_to_home(self):
        resp = self.client.post(
            reverse("pages:set_court"),
            {"court": "north-dakota", "next": "https://evil.example/x"},
        )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.url, reverse("pages:home"))

    def test_get_is_404(self):
        self.assertEqual(
            self.client.get(reverse("pages:set_court")).status_code, 404
        )

    @override_settings(DEPLOYMENT_ENV="prod")
    def test_disabled_in_prod_is_404(self):
        resp = self.client.post(
            reverse("pages:set_court"), {"court": "north-dakota"}
        )
        self.assertEqual(resp.status_code, 404)


@pytest.mark.postgres
class ChatPageActiveCourtTests(TestCase):
    """chat_page resolves court from the session, param overrides + persists."""

    def test_uses_session_active_court(self):
        session = self.client.session
        session[cc.SESSION_KEY] = "north-dakota"
        session.save()
        resp = self.client.get(
            reverse("pages:chat") + "?topic=adult_name_change"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["court_slug"], "north-dakota")
        self.assertTrue(resp.context["court_name"])

    def test_explicit_court_param_overrides_and_persists(self):
        session = self.client.session
        session[cc.SESSION_KEY] = "north-dakota"
        session.save()
        resp = self.client.get(
            reverse("pages:chat") + "?topic=eviction&court=dupage-il"
        )
        self.assertEqual(resp.context["court_slug"], "dupage-il")
        self.assertEqual(self.client.session[cc.SESSION_KEY], "dupage-il")
