"""Tests for app middleware.

The site gate tests are DB-free except the one that opens the site,
which saves a session; the session key and identity test classes are
postgres-marked.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase

from litigant_portal.app.middleware import IdentityMiddleware
from litigant_portal.app.models import UserIdentity

User = get_user_model()


@pytest.mark.postgres
class AnonymousSessionKeyMiddlewareTests(TestCase):
    """Tests for session key preservation on anonymous requests."""

    def test_anonymous_user_gets_session_key_stored(self):
        """Middleware should store session_key in session data for anon users."""
        # Force session creation by setting a value
        session = self.client.session
        session["force_create"] = True
        session.save()
        self.client.cookies["sessionid"] = session.session_key

        self.client.get("/")

        self.assertEqual(
            self.client.session["_anonymous_session_key"],
            self.client.session.session_key,
        )

    def test_authenticated_user_skips_storage(self):
        """Middleware should not store key for authenticated users."""
        User.objects.create_user(username="testuser", password="testpass")
        self.client.login(username="testuser", password="testpass")

        self.client.get("/")

        self.assertNotIn("_anonymous_session_key", self.client.session)

    def test_no_session_key_skips_storage(self):
        """Middleware should not store key when session has no key yet."""
        # Fresh client with no prior session — session_key is None
        self.client.get("/")

        self.assertNotIn("_anonymous_session_key", self.client.session)

    def test_logged_in_with_an_empty_anonymous_identity_forgets_it(self):
        empty = UserIdentity.objects.create(session_key="before-login")
        user = User.objects.create_user(username="testuser", password="p")
        self.client.force_login(user)
        session = self.client.session
        session["_anonymous_session_key"] = "before-login"
        session.save()

        self.assertEqual(self.client.get("/about/").status_code, 200)

        self.assertNotIn("_anonymous_session_key", self.client.session)
        self.assertFalse(UserIdentity.objects.filter(pk=empty.pk).exists())


@pytest.mark.postgres
class IdentityMiddlewareTests(TestCase):
    """Tests for the lazy request.identity attachment."""

    def _request(self, user=None):
        request = RequestFactory().get("/")
        SessionMiddleware(lambda r: None).process_request(request)
        request.user = user or AnonymousUser()
        return request

    def test_identity_is_lazy_until_accessed(self):
        request = self._request()
        IdentityMiddleware(lambda r: None)(request)
        # Attached, but the get-or-create has not run yet.
        self.assertEqual(UserIdentity.objects.count(), 0)
        # First access resolves it (and creates the anonymous identity).
        self.assertIsNone(request.identity.user)
        self.assertEqual(UserIdentity.objects.count(), 1)

    def test_authenticated_request_resolves_to_user_identity(self):
        user = User.objects.create_user(username="u", password="p")
        request = self._request(user=user)
        IdentityMiddleware(lambda r: None)(request)
        self.assertEqual(request.identity.user, user)

    def test_resolution_is_memoized_per_request(self):
        request = self._request()
        IdentityMiddleware(lambda r: None)(request)
        first_pk = request.identity.pk
        self.assertEqual(request.identity.pk, first_pk)
        self.assertEqual(UserIdentity.objects.count(), 1)


SITE_PASSWORD = "letmein-test"


@pytest.fixture
def site_gate(settings):
    settings.SITE_PASSWORD = SITE_PASSWORD


def test_site_gate_shows_password_page(site_gate, client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"This site is under development" in response.content


def test_site_gate_rejects_wrong_password(site_gate, client):
    response = client.post("/", {"site_password": "wrong"})
    assert response.status_code == 200
    assert b"Incorrect password." in response.content


def test_site_gate_lets_api_through(site_gate, client):
    response = client.get("/api/health/")
    assert b"This site is under development" not in response.content


def test_site_gate_refuses_even_the_right_password_after_ten_attempts(
    site_gate, ratelimited, client
):
    for _ in range(10):
        client.post("/", {"site_password": "wrong"})

    response = client.post("/", {"site_password": SITE_PASSWORD})
    assert response.status_code == 429
    assert b"Too many attempts." in response.content


def test_site_gate_counts_each_viewer_address_apart(
    site_gate, ratelimited, behind_cloudfront, client
):
    viewer_a = {"CloudFront-Viewer-Address": "203.0.113.10:5000"}
    viewer_b = {"CloudFront-Viewer-Address": "203.0.113.20:5000"}
    for _ in range(10):
        client.post("/", {"site_password": "wrong"}, headers=viewer_a)

    response = client.post("/", {"site_password": "wrong"}, headers=viewer_a)
    assert response.status_code == 429

    response = client.post("/", {"site_password": "wrong"}, headers=viewer_b)
    assert response.status_code == 200
    assert b"Incorrect password." in response.content


@pytest.mark.postgres
@pytest.mark.django_db
def test_site_gate_correct_password_opens_the_site(site_gate, client):
    response = client.post("/chat/", {"site_password": SITE_PASSWORD})
    assert response.status_code == 302
    assert response["Location"] == "/chat/"
    assert client.session["site_password_ok"] is True
