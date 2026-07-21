"""
Tests for the Litigant Portal.

Tests custom application logic only - not Django built-ins.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.management import call_command
from django.test import Client, RequestFactory, SimpleTestCase, TestCase

from litigant_portal.app.context_processors import toast_messages

User = get_user_model()


class DjangoSystemTests(SimpleTestCase):
    """Verify Django configuration is correct."""

    def test_system_checks_pass(self):
        """Django system checks should pass without warnings."""
        # This catches misconfigurations early
        call_command("check", "--fail-level", "WARNING")


# =============================================================================
# Route Tests
# =============================================================================


@pytest.mark.postgres
class HomePageTests(TestCase):
    """Tests for the dashboard home page at /."""

    def setUp(self):
        self.client = Client()

    def test_home_has_footer(self):
        """Home page should render the footer."""
        response = self.client.get("/")
        self.assertContains(response, "mobile-footer")

    def test_home_does_not_have_chat_interface(self):
        """Home page should not include the chat Alpine component."""
        response = self.client.get("/")
        self.assertNotContains(response, "homePage")


@pytest.mark.postgres
class ChatPageTests(TestCase):
    """Tests for the chat page at /chat/."""

    def setUp(self):
        self.client = Client()

    def test_chat_page_renders(self):
        """Chat page should return 200 with the chat app mounted."""
        response = self.client.get("/chat/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "chatApp")

    def test_chat_page_has_no_footer(self):
        """Chat page should suppress the footer."""
        response = self.client.get("/chat/")
        self.assertNotContains(response, "mobile-footer")


# =============================================================================
# Auth Template Tests
# =============================================================================


@pytest.mark.postgres
class LoginPageTests(TestCase):
    """Tests for custom login page template (templates/account/login.html)."""

    def setUp(self):
        self.client = Client()

    def test_login_page_has_custom_heading(self):
        """Login page should show our custom heading, not allauth default."""
        response = self.client.get("/accounts/login/")
        self.assertContains(response, "Sign in")

    def test_login_page_has_signup_link(self):
        """Login page should link to signup page."""
        response = self.client.get("/accounts/login/")
        self.assertContains(response, "/accounts/signup/")


@pytest.mark.postgres
class SignupPageTests(TestCase):
    """Tests for custom signup page template (templates/account/signup.html)."""

    def setUp(self):
        self.client = Client()

    def test_signup_page_has_custom_heading(self):
        """Signup page should show our custom heading."""
        response = self.client.get("/accounts/signup/")
        self.assertContains(response, "Create account")

    def test_signup_page_has_login_link(self):
        """Signup page should link to login page."""
        response = self.client.get("/accounts/signup/")
        self.assertContains(response, "/accounts/login/")


@pytest.mark.postgres
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
        """Logout page should show our custom template, not allauth default."""
        self.client.login(username="testuser", password="testpass123")
        response = self.client.get("/accounts/logout/")
        self.assertContains(response, "Sign out")


# =============================================================================
# User Menu Tests (Header Auth UI)
# =============================================================================


@pytest.mark.postgres
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


@pytest.mark.postgres
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

    def test_header_does_not_expose_user_email(self):
        """Header must not render the user's email (PII privacy — #273, #304)."""
        response = self.client.get("/")
        self.assertNotContains(response, "test@example.com")

    def test_header_shows_sign_out_link(self):
        """Header should show 'Sign out' option when logged in."""
        response = self.client.get("/")
        self.assertContains(response, "Sign out")
        self.assertContains(response, "/accounts/logout/")


# =============================================================================
# Auth Flow Tests
# =============================================================================


@pytest.mark.postgres
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


@pytest.mark.postgres
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
        from litigant_portal.app.models import UserProfile

        profile = UserProfile.objects.create(user=self.user, name="Jane Doe")
        self.assertEqual(str(profile), "Jane Doe (test@example.com)")

    def test_str_without_name(self):
        """__str__ should show 'Unnamed' when name is empty."""
        from litigant_portal.app.models import UserProfile

        profile = UserProfile.objects.create(user=self.user)
        self.assertEqual(str(profile), "Unnamed (test@example.com)")

    def test_full_address_empty_when_no_address(self):
        """full_address should return empty string when no address_line1."""
        from litigant_portal.app.models import UserProfile

        profile = UserProfile.objects.create(user=self.user, city="Boston")
        self.assertEqual(profile.full_address, "")

    def test_full_address_single_line(self):
        """full_address should return just street when no city/state."""
        from litigant_portal.app.models import UserProfile

        profile = UserProfile.objects.create(
            user=self.user, address_line1="123 Main St"
        )
        self.assertEqual(profile.full_address, "123 Main St")

    def test_full_address_with_unit(self):
        """full_address should include address_line2 when present."""
        from litigant_portal.app.models import UserProfile

        profile = UserProfile.objects.create(
            user=self.user,
            address_line1="123 Main St",
            address_line2="Apt 4B",
        )
        self.assertEqual(profile.full_address, "123 Main St\nApt 4B")

    def test_full_address_complete(self):
        """full_address should format complete address correctly."""
        from litigant_portal.app.models import UserProfile

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


@pytest.mark.postgres
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
        from litigant_portal.app.models import UserProfile

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
        from litigant_portal.app.models import UserProfile

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
# Footer & Navigation Tests
# =============================================================================


@pytest.mark.postgres
class FooterLinkTests(TestCase):
    """Tests for footer links on the home page."""

    def setUp(self):
        self.client = Client()

    def test_footer_has_about_link(self):
        """Footer should link to the about page."""
        response = self.client.get("/")
        self.assertContains(response, "/about/")

    def test_footer_has_privacy_link(self):
        """Footer should link to the privacy page."""
        response = self.client.get("/")
        self.assertContains(response, "/privacy/")

    def test_footer_has_accessibility_link(self):
        """Footer should link to the accessibility page."""
        response = self.client.get("/")
        self.assertContains(response, "/accessibility/")

    def test_footer_has_free_law_link(self):
        """Footer should link to free.law."""
        response = self.client.get("/")
        self.assertContains(response, "https://free.law")


# =============================================================================
# Topic Detail Page Tests
# =============================================================================


@pytest.mark.postgres
class TopicDetailTests(TestCase):
    """Tests for topic detail pages at /topics/<slug>/."""

    def setUp(self):
        self.client = Client()

    def test_all_topics_render_with_correct_context(self):
        """Each topic slug should return 200 with its title from TOPICS.

        Eviction is excluded: it has reached engine parity, so /topics/eviction/
        redirects to chat instead (test_eviction_detail_redirects_to_chat).
        """
        from litigant_portal.app.views import TOPICS

        for slug, topic in TOPICS.items():
            if slug == "eviction":
                continue
            with self.subTest(slug=slug):
                response = self.client.get(f"/topics/{slug}/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context["topic"], topic)

    def test_topic_detail_passes_slug(self):
        """Topic detail page should pass slug in template context."""
        response = self.client.get("/topics/adult_name_change/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["slug"], "adult_name_change")

    def test_eviction_detail_redirects_to_chat(self):
        """Eviction reached engine parity: its static page is retired and the
        URL now redirects to the chat entry (#611)."""
        response = self.client.get("/topics/eviction/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("topic=eviction", response.url)

    def test_invalid_slug_returns_404(self):
        """An unknown topic slug should return 404."""
        response = self.client.get("/topics/nonexistent/")
        self.assertEqual(response.status_code, 404)


# =============================================================================
# Deep-link Entry Tests (#327)
# =============================================================================


@pytest.mark.postgres
class DeepLinkTests(TestCase):
    """Tests for /t/{court}/{topic}/ deep-link entry."""

    def setUp(self):
        self.client = Client()

    def test_valid_court_and_topic_redirects_to_chat(self):
        """Valid pair redirects to /chat/ with both params set."""
        response = self.client.get("/t/north-dakota/adult_name_change/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("topic=adult_name_change", response.url)
        self.assertIn("court=north-dakota", response.url)

    def test_unknown_court_returns_404(self):
        response = self.client.get("/t/xx/adult_name_change/")
        self.assertEqual(response.status_code, 404)

    def test_unknown_topic_returns_404(self):
        response = self.client.get("/t/north-dakota/not_a_topic/")
        self.assertEqual(response.status_code, 404)

    def test_deep_link_oh_eviction(self):
        """Second registered pair (Franklin County OH + eviction) also works."""
        response = self.client.get("/t/franklin-county-oh/eviction/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("topic=eviction", response.url)
        self.assertIn("court=franklin-county-oh", response.url)

    def test_legacy_underscore_court_slug_returns_404(self):
        """Pre-#338 internal slugs like 'nd' / 'franklin_county_oh' are no
        longer registered — only the canonical hyphenated slugs work."""
        for legacy in (
            "/t/nd/adult_name_change/",
            "/t/franklin_county_oh/eviction/",
        ):
            response = self.client.get(legacy)
            self.assertEqual(
                response.status_code,
                404,
                msg=f"Legacy slug {legacy!r} should 404 after #338",
            )

    def test_every_registered_court_resolves_via_deep_link(self):
        """#332-style round-trip: every court directory under
        chat/prompts/courts/ must be reachable via /t/{court}/{topic}/, and
        must use canonical hyphenated slugs (no underscores). Catches a future
        court being added under a non-canonical slug."""
        from litigant_portal.prompts import _PROMPTS_DIR

        courts = sorted(
            p.name
            for p in (_PROMPTS_DIR / "courts").iterdir()
            if p.is_dir() and (p / "prompt.md").is_file()
        )
        topics = sorted(
            p.name
            for p in (_PROMPTS_DIR / "topics").iterdir()
            if p.is_dir() and (p / "prompt.md").is_file()
        )
        self.assertTrue(courts, "Expected at least one registered court")
        self.assertTrue(topics, "Expected at least one registered topic")
        # Pick any registered topic for the round-trip — we're testing court
        # resolution, not topic.
        topic = topics[0]
        for court in courts:
            self.assertNotIn(
                "_",
                court,
                msg=f"Court slug {court!r} must use hyphens, not underscores",
            )
            response = self.client.get(f"/t/{court}/{topic}/")
            self.assertEqual(
                response.status_code,
                302,
                msg=f"Registered court {court!r} should resolve via deep-link",
            )
            self.assertIn(f"court={court}", response.url)


# =============================================================================
# Context Processor Tests
# =============================================================================


@pytest.mark.postgres
class ToastMessagesTests(TestCase):
    """Tests for toast_messages context processor tag-to-variant mapping."""

    def setUp(self):
        self.factory = RequestFactory()

    def _request_with_messages(self, *tags_and_texts):
        """Create a request with messages added via the messages framework."""
        request = self.factory.get("/")
        request.session = self.client.session
        request._messages = FallbackStorage(request)
        from django.contrib.messages import constants

        tag_map = {
            "success": constants.SUCCESS,
            "error": constants.ERROR,
            "warning": constants.WARNING,
            "info": constants.INFO,
        }
        for tag, text in tags_and_texts:
            request._messages.add(tag_map.get(tag, constants.INFO), text)
        return request

    def test_no_messages_returns_empty_list(self):
        request = self._request_with_messages()

        result = toast_messages(request)

        self.assertEqual(result["toast_messages"], [])

    def test_error_tag_maps_to_danger_variant(self):
        request = self._request_with_messages(("error", "Something broke"))

        result = toast_messages(request)

        self.assertEqual(result["toast_messages"][0]["variant"], "danger")
        self.assertEqual(
            result["toast_messages"][0]["text"], "Something broke"
        )

    def test_success_tag_passes_through(self):
        request = self._request_with_messages(("success", "Saved"))

        result = toast_messages(request)

        self.assertEqual(result["toast_messages"][0]["variant"], "success")

    def test_warning_tag_passes_through(self):
        request = self._request_with_messages(("warning", "Check this"))

        result = toast_messages(request)

        self.assertEqual(result["toast_messages"][0]["variant"], "warning")
