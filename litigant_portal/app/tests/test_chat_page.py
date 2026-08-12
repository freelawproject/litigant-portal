"""Tests for the chat page rendering inside the shared site frame.

These pin the contract: no `chat_header.html` override on the chat page
itself (`pages/admin/index.html` still depends on that file - see
`AdminHeaderRegressionTests`), the Briefcase agent-state aside gated
server-side to the `manage_developers` permission, an accessible live
region on the messages container, and a handful of Tailwind hygiene
swaps.
"""

import re
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from litigant_portal.app.permissions import DEVELOPERS_GROUP

TEMPLATE_PATH = Path("litigant_portal/app/templates/pages/chat/index.html")
MAIN_CSS_PATH = Path("litigant_portal/app/src/main.css")
AGENT_STATE_PATH = Path(
    "litigant_portal/app/templates/pages/chat/partials/_agent_state.html"
)

# Markup unique to the default site header (cotton/organisms/header.html) —
# absent from the bespoke chat_header.html override.
DEFAULT_HEADER_MARKER = "mobile-header-inner"

# Markup unique to _agent_state.html (the Briefcase aside body).
AGENT_STATE_MARKER = "No state yet."

# The Briefcase heading/trigger chrome around _agent_state.html — gating
# only the include isn't enough, the whole aside/button must be gated too.
# Word-boundary so this doesn't match `openBriefcase`/`closeBriefcase`, the
# Alpine method names used by an unrelated, always-rendered backdrop div.
BRIEFCASE_CHROME_RE = re.compile(r"\bBriefcase\b")

# A single element carrying both `role="log"` and `aria-live="polite"`,
# in either attribute order.
LIVE_REGION_RE = re.compile(
    r'<[a-zA-Z][^<>]*role="log"[^<>]*aria-live="polite"[^<>]*>'
    r'|<[a-zA-Z][^<>]*aria-live="polite"[^<>]*role="log"[^<>]*>'
)

# Opening tags for elements that render visible prose (not icon/decorative
# wrappers): headings and paragraphs.
TEXT_TAG_OPEN_RE = re.compile(r"<(p|h[1-6])\b")


@pytest.mark.postgres
class ChatPageRouteTests(TestCase):
    """GET /chat/ renders the chat page template for anyone."""

    def setUp(self):
        self.client = Client()

    def test_chat_page_returns_200(self):
        response = self.client.get(reverse("pages:chat"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/chat/index.html")


@pytest.mark.postgres
class ChatPageHeaderFrameTests(TestCase):
    """No `header` block override in the chat template, so `<c-organisms.header />` (not chat_header.html) renders."""

    def test_default_header_markup_renders_on_chat_page(self):
        response = self.client.get(reverse("pages:chat"))
        self.assertIn(DEFAULT_HEADER_MARKER, response.content.decode())


@pytest.mark.postgres
class AdminHeaderRegressionTests(TestCase):
    """`pages/admin/index.html` still depends on `chat_header.html` — deleting it would break `/admin`."""

    def test_admin_page_renders_successfully_with_chat_header(self):
        User = get_user_model()
        User.objects.create_superuser(
            username="admin_root",
            email="admin_root@example.com",
            password="pw",
        )
        client = Client()
        client.login(username="admin_root", password="pw")
        response = client.get(reverse("pages:admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/admin/index.html")
        # Admin still uses its own header, not the default.
        self.assertNotIn(DEFAULT_HEADER_MARKER, response.content.decode())


@pytest.mark.postgres
class AgentStateGatingTests(TestCase):
    """The Briefcase agent-state aside is only present in the response body
    for users holding `manage_developers` — server-side gated, not just
    CSS/Alpine-hidden."""

    def setUp(self):
        self.client = Client()
        User = get_user_model()
        developers = Group.objects.get(name=DEVELOPERS_GROUP)
        self.developer = User.objects.create_user(
            username="dev", email="dev@example.com", password="pw"
        )
        self.developer.groups.add(developers)
        self.regular_user = User.objects.create_user(
            username="regular", email="regular@example.com", password="pw"
        )

    def test_anonymous_user_does_not_see_agent_state(self):
        response = self.client.get(reverse("pages:chat"))
        content = response.content.decode()
        self.assertNotIn(AGENT_STATE_MARKER, content)
        self.assertNotRegex(content, BRIEFCASE_CHROME_RE)

    def test_non_developer_does_not_see_agent_state(self):
        self.client.login(username="regular", password="pw")
        response = self.client.get(reverse("pages:chat"))
        content = response.content.decode()
        self.assertNotIn(AGENT_STATE_MARKER, content)
        self.assertNotRegex(content, BRIEFCASE_CHROME_RE)

    def test_developer_sees_agent_state(self):
        self.client.login(username="dev", password="pw")
        response = self.client.get(reverse("pages:chat"))
        content = response.content.decode()
        self.assertIn(AGENT_STATE_MARKER, content)
        self.assertRegex(content, BRIEFCASE_CHROME_RE)

    def test_developer_sees_agent_state_in_both_inline_and_drawer_variants(
        self,
    ):
        self.client.login(username="dev", password="pw")
        response = self.client.get(reverse("pages:chat"))
        content = response.content.decode()
        # _agent_state.html is included twice: inline sidebar + drawer.
        self.assertEqual(content.count(AGENT_STATE_MARKER), 2)


@pytest.mark.postgres
class MessagesLiveRegionTests(TestCase):
    """The messages container is an accessible live region: `role="log"`
    and `aria-live="polite"` on the *same* element, not just present
    somewhere in the page."""

    def test_messages_container_has_role_log_and_aria_live_polite(self):
        response = self.client.get(reverse("pages:chat"))
        content = response.content.decode()
        self.assertRegex(
            content,
            LIVE_REGION_RE,
            'Expected a single element with both role="log" and '
            'aria-live="polite" (found the strings only separately, if '
            "at all).",
        )


class ChatTemplateHygieneTests(TestCase):
    """Source-level checks for Tailwind hygiene: contrast, min-h tokens, and arbitrary text-size values."""

    def setUp(self):
        self.template_source = TEMPLATE_PATH.read_text()
        self.template_lines = self.template_source.splitlines()

    def test_text_color_greyscale_400_replaced_with_500_on_text_elements(self):
        # Icon/decorative uses of greyscale-400 stay as-is; only lines
        # rendering visible text should flip to -500.
        lines = self.template_lines
        offending = []
        for i, line in enumerate(lines):
            if "text-greyscale-400" not in line or "c-atoms.icon" in line:
                continue
            if "{% trans" in line or "x-text=" in line:
                offending.append(line.strip())
                continue
            if TEXT_TAG_OPEN_RE.search(line):
                lookahead = lines[i + 1 : i + 4]
                if any("{% trans" in nxt for nxt in lookahead):
                    offending.append(line.strip())
        self.assertEqual(
            offending,
            [],
            "text-color use of greyscale-400 should be greyscale-500:\n"
            + "\n".join(offending),
        )

    def test_min_h_3_25rem_arbitrary_value_replaced(self):
        self.assertNotIn("min-h-[3.25rem]", self.template_source)
        self.assertIn("min-h-13", self.template_source)

    def test_min_h_4_5rem_arbitrary_value_replaced(self):
        self.assertNotIn("min-h-[4.5rem]", self.template_source)
        self.assertIn("min-h-18", self.template_source)

    def test_arbitrary_text_size_values_replaced_with_text_2xs_token(self):
        self.assertNotIn("text-[9px]", self.template_source)
        self.assertNotIn("text-[10px]", self.template_source)
        self.assertNotIn("text-[11px]", self.template_source)
        self.assertIn("text-2xs", self.template_source)

    def test_text_2xs_theme_token_added_to_main_css(self):
        css_source = MAIN_CSS_PATH.read_text()
        self.assertIn("--text-2xs", css_source)

    def test_agent_state_partial_contrast_left_untouched(self):
        # Accepted gap: _agent_state.html's own greyscale-400 text is out
        # of scope for this phase, since that partial requires manage_developers.
        self.assertIn("text-greyscale-400", AGENT_STATE_PATH.read_text())
