"""Tests for app middleware."""

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
