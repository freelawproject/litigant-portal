"""Tests for AnonymousSessionKeyMiddleware."""

from django.contrib.auth import get_user_model
from django.test import TestCase

User = get_user_model()


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
