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
# Route Tests
# =============================================================================


class HomePageTests(TestCase):
    """Tests for the dashboard home page at /."""

    def setUp(self):
        self.client = Client()

    def test_home_returns_dashboard(self):
        """Home page should render the dashboard with topic grid."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Browse by Topic")

    def test_home_has_hero(self):
        """Home page should include the hero section."""
        response = self.client.get("/")
        self.assertContains(response, "How can we help you today?")

    def test_home_has_footer(self):
        """Home page should render the footer."""
        response = self.client.get("/")
        self.assertContains(response, "mobile-footer")

    def test_home_does_not_have_chat_interface(self):
        """Home page should not include the chat Alpine component."""
        response = self.client.get("/")
        self.assertNotContains(response, "homePage")


class ChatPageTests(TestCase):
    """Tests for the chat page at /chat/."""

    def setUp(self):
        self.client = Client()

    def test_chat_page_renders(self):
        """Chat page should return 200 with chat interface."""
        response = self.client.get("/chat/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "homePage")

    def test_chat_page_has_no_footer(self):
        """Chat page should suppress the footer."""
        response = self.client.get("/chat/")
        self.assertNotContains(response, "mobile-footer")

    def test_chat_page_has_overflow_hidden(self):
        """Chat page should set overflow-hidden on body."""
        response = self.client.get("/chat/")
        self.assertContains(response, "overflow-hidden")


# =============================================================================
# Auth Template Tests
# =============================================================================


class LoginPageTests(TestCase):
    """Tests for custom login page template (templates/account/login.html)."""

    def setUp(self):
        self.client = Client()

    def test_login_page_has_custom_heading(self):
        """Login page should show our custom heading, not allauth default."""
        response = self.client.get("/accounts/login/")
        self.assertContains(response, "Sign in")
        self.assertContains(response, "Access your legal assistance portal")

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

    def test_signup_page_has_custom_heading(self):
        """Signup page should show our custom heading."""
        response = self.client.get("/accounts/signup/")
        self.assertContains(response, "Create account")
        self.assertContains(response, "Get free legal assistance today")

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

    def test_user_is_logged_out_after_logout(self):
        """User should be anonymous after logout."""
        self.client.post("/accounts/logout/")
        # Subsequent request should show sign-in link (anonymous)
        response = self.client.get("/")
        self.assertContains(response, "Sign in")
        self.assertNotContains(response, "test@example.com")


# =============================================================================
# Profile Tests
# =============================================================================


class UserProfileModelTests(TestCase):
    """Tests for UserProfile model custom logic."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_str_with_name(self):
        """__str__ should show name and email when name is set."""
        from portal.models import UserProfile

        profile = UserProfile.objects.create(user=self.user, name="Jane Doe")
        self.assertEqual(str(profile), "Jane Doe (test@example.com)")

    def test_str_without_name(self):
        """__str__ should show 'Unnamed' when name is empty."""
        from portal.models import UserProfile

        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(str(profile), "Unnamed (test@example.com)")

    def test_full_address_empty_when_no_address(self):
        """full_address should return empty string when no address_line1."""
        from portal.models import UserProfile

        profile = UserProfile.objects.create(user=self.user, city="Boston")
        self.assertEqual(profile.full_address, "")

    def test_full_address_single_line(self):
        """full_address should return just street when no city/state."""
        from portal.models import UserProfile

        profile = UserProfile.objects.create(
            user=self.user, address_line1="123 Main St"
        )
        self.assertEqual(profile.full_address, "123 Main St")

    def test_full_address_with_unit(self):
        """full_address should include address_line2 when present."""
        from portal.models import UserProfile

        profile = UserProfile.objects.create(
            user=self.user,
            address_line1="123 Main St",
            address_line2="Apt 4B",
        )
        self.assertEqual(profile.full_address, "123 Main St\nApt 4B")

    def test_full_address_complete(self):
        """full_address should format complete address correctly."""
        from portal.models import UserProfile

        profile = UserProfile.objects.create(
            user=self.user,
            address_line1="123 Main St",
            address_line2="Apt 4B",
            city="Boston",
            state="MA",
            zip_code="02101",
        )
        self.assertEqual(
            profile.full_address,
            "123 Main St\nApt 4B\nBoston, MA 02101",
        )


class ProfileViewTests(TestCase):
    """Tests for profile views."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_profile_requires_login(self):
        """Profile page should redirect anonymous users."""
        response = self.client.get("/profile/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_profile_edit_requires_login(self):
        """Profile edit page should redirect anonymous users."""
        response = self.client.get("/profile/edit/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_profile_creates_profile_if_missing(self):
        """Viewing profile should create one if user doesn't have one."""
        from portal.models import UserProfile

        self.client.login(username="testuser", password="testpass123")
        self.assertFalse(UserProfile.objects.filter(user=self.user).exists())

        response = self.client.get("/profile/")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())

    def test_profile_displays_user_email(self):
        """Profile page should display the user's email."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/profile/")
        self.assertContains(response, "test@example.com")

    def test_profile_edit_saves_data(self):
        """Profile edit should save form data."""
        from portal.models import UserProfile

        self.client.login(username="testuser", password="testpass123")
        response = self.client.post(
            "/profile/edit/",
            {
                "name": "Jane Doe",
                "phone": "555-1234",
                "city": "Boston",
                "state": "MA",
            },
        )
        self.assertEqual(response.status_code, 302)

        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.name, "Jane Doe")
        self.assertEqual(profile.phone, "555-1234")
        self.assertEqual(profile.city, "Boston")
        self.assertEqual(profile.state, "MA")


# =============================================================================
# Agent Test Page Tests
# =============================================================================


class AgentTestPageTests(TestCase):
    """Tests for the /test/<agent_name>/ route."""

    def setUp(self):
        self.client = Client()

    def test_agent_page_renders_chat(self):
        """Known agent should render chat interface with agent name."""
        response = self.client.get("/test/WeatherAgent/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "homePage")

    def test_unknown_agent_returns_404(self):
        """Unknown agent name should return 404."""
        response = self.client.get("/test/nonexistent/")
        self.assertEqual(response.status_code, 404)
