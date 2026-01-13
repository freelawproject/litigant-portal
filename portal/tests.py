"""
Tests for the Litigant Portal.

Tests custom application logic only - not Django built-ins.
"""

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase

User = get_user_model()


class DjangoSystemTests(TestCase):
    """Verify Django configuration is correct."""

    def test_system_checks_pass(self):
        """Django system checks should pass without warnings."""
        # This catches misconfigurations early
        call_command("check", "--fail-level", "WARNING")


# =============================================================================
# Auth Template Tests
# =============================================================================


class LoginPageTests(TestCase):
    """Tests for custom login page template (templates/account/login.html)."""

    def setUp(self):
        self.client = Client()

    def test_login_page_renders(self):
        """Login page should return 200 status."""
        response = self.client.get("/accounts/login/")
        self.assertEqual(response.status_code, 200)

    def test_login_page_has_custom_heading(self):
        """Login page should show our custom heading, not allauth default."""
        response = self.client.get("/accounts/login/")
        self.assertContains(response, "Sign in")
        self.assertContains(response, "Access your legal assistance portal")

    def test_login_page_has_email_field(self):
        """Login page should have email input field."""
        response = self.client.get("/accounts/login/")
        self.assertContains(response, 'name="login"')
        self.assertContains(response, 'type="email"')

    def test_login_page_has_signup_link(self):
        """Login page should link to signup page."""
        response = self.client.get("/accounts/login/")
        self.assertContains(response, "Don't have an account?")
        self.assertContains(response, "/accounts/signup/")

    def test_login_page_has_password_reset_link(self):
        """Login page should link to password reset."""
        response = self.client.get("/accounts/login/")
        self.assertContains(response, "Forgot your password?")


class SignupPageTests(TestCase):
    """Tests for custom signup page template (templates/account/signup.html)."""

    def setUp(self):
        self.client = Client()

    def test_signup_page_renders(self):
        """Signup page should return 200 status."""
        response = self.client.get("/accounts/signup/")
        self.assertEqual(response.status_code, 200)

    def test_signup_page_has_custom_heading(self):
        """Signup page should show our custom heading."""
        response = self.client.get("/accounts/signup/")
        self.assertContains(response, "Create account")
        self.assertContains(response, "Get free legal assistance today")

    def test_signup_page_has_email_field(self):
        """Signup page should have email input field."""
        response = self.client.get("/accounts/signup/")
        self.assertContains(response, 'name="email"')

    def test_signup_page_has_password_fields(self):
        """Signup page should have both password fields."""
        response = self.client.get("/accounts/signup/")
        self.assertContains(response, 'name="password1"')
        self.assertContains(response, 'name="password2"')

    def test_signup_page_has_login_link(self):
        """Signup page should link to login page."""
        response = self.client.get("/accounts/signup/")
        self.assertContains(response, "Already have an account?")
        self.assertContains(response, "/accounts/login/")


class LogoutPageTests(TestCase):
    """Tests for custom logout page template (templates/account/logout.html)."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_logout_page_requires_login(self):
        """Logout page should redirect anonymous users to login."""
        response = self.client.get("/accounts/logout/")
        self.assertEqual(response.status_code, 302)

    def test_logout_page_renders_for_authenticated_user(self):
        """Logout page should render for logged-in users."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/accounts/logout/")
        self.assertEqual(response.status_code, 200)

    def test_logout_page_has_confirmation_message(self):
        """Logout page should show confirmation prompt."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/accounts/logout/")
        self.assertContains(response, "Sign out")
        self.assertContains(response, "Are you sure you want to sign out?")

    def test_logout_page_has_cancel_button(self):
        """Logout page should have cancel option."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/accounts/logout/")
        self.assertContains(response, "Cancel")


# =============================================================================
# User Menu Tests (Header Auth UI)
# =============================================================================


class UserMenuAnonymousTests(TestCase):
    """Tests for user menu when user is not logged in."""

    def setUp(self):
        self.client = Client()

    def test_header_shows_sign_in_link(self):
        """Header should show 'Sign in' link for anonymous users."""
        response = self.client.get("/")
        self.assertContains(response, "Sign in")
        self.assertContains(response, "/accounts/login/")

    def test_header_does_not_show_sign_out(self):
        """Header should not show 'Sign out' for anonymous users."""
        response = self.client.get("/")
        self.assertNotContains(response, "Sign out")


class UserMenuAuthenticatedTests(TestCase):
    """Tests for user menu when user is logged in."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client.login(username="testuser", password="testpass123")

    def test_header_shows_user_email(self):
        """Header should display user's email when logged in."""
        response = self.client.get("/")
        self.assertContains(response, "test@example.com")

    def test_header_shows_sign_out_link(self):
        """Header should show 'Sign out' option when logged in."""
        response = self.client.get("/")
        self.assertContains(response, "Sign out")
        self.assertContains(response, "/accounts/logout/")


# =============================================================================
# Auth Flow Tests
# =============================================================================


class SignupFlowTests(TestCase):
    """Tests for the signup flow using our custom templates."""

    def setUp(self):
        self.client = Client()

    def test_signup_creates_user_and_redirects(self):
        """Successful signup should create user and redirect to home."""
        response = self.client.post(
            "/accounts/signup/",
            {
                "email": "newuser@example.com",
                "password1": "securepass123!",
                "password2": "securepass123!",
            },
        )
        # Should redirect to home after signup
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")
        # User should be created
        self.assertTrue(
            User.objects.filter(email="newuser@example.com").exists()
        )


class LoginFlowTests(TestCase):
    """Tests for the login flow using our custom templates."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_login_redirects_to_home(self):
        """Successful login should redirect to home page."""
        response = self.client.post(
            "/accounts/login/",
            {"login": "test@example.com", "password": "testpass123"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_login_invalid_credentials_shows_error(self):
        """Invalid login should show error on same page."""
        response = self.client.post(
            "/accounts/login/",
            {"login": "test@example.com", "password": "wrongpassword"},
        )
        self.assertEqual(response.status_code, 200)
        # Should show error message (allauth's error text)
        self.assertContains(response, "email address and/or password")


class LogoutFlowTests(TestCase):
    """Tests for the logout flow using our custom templates."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.client.login(username="testuser", password="testpass123")

    def test_logout_post_redirects_to_home(self):
        """POST to logout should sign out and redirect to home."""
        response = self.client.post("/accounts/logout/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_user_is_logged_out_after_logout(self):
        """User should be anonymous after logout."""
        self.client.post("/accounts/logout/")
        # Subsequent request should show sign-in link (anonymous)
        response = self.client.get("/")
        self.assertContains(response, "Sign in")
        self.assertNotContains(response, "test@example.com")
