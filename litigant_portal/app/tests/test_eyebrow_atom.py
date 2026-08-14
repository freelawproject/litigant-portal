"""Tests for the c-atoms.eyebrow atom.

Cotton tags compile only through django_cotton's loader, so these exercise the
atom through the pages that use it rather than in isolation. Between them the
chat page, the admin page, and the style guide cover every prop: with an icon
and without, explicit levels 2 and 4 and the default.
"""

import re
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from litigant_portal.app.permissions import ADMINS_GROUP, DEVELOPERS_GROUP

CHAT_TEMPLATE_PATH = Path(
    "litigant_portal/app/templates/pages/chat/index.html"
)
ADMIN_TEMPLATE_PATH = Path(
    "litigant_portal/app/templates/pages/admin/index.html"
)

# A heading carrying the typography the atom owns is a hand-rolled eyebrow.
# Lookaheads so class order and color don't matter. The atom is exempt
# because its level is interpolated (<h{{ level }}), and non-heading uses of
# the same classes (the <tr> in admin/users.html) aren't eyebrows.
HANDROLLED_EYEBROW_RE = re.compile(
    r"<h[2-6](?=[^>]*\buppercase\b)(?=[^>]*\btracking-wider\b)[^>]*>"
)


def _heading_count(content, label, level=r"[2-6]"):
    """Count headings, not substrings — the labels recur in aria-labels."""
    pattern = rf"<h({level})\b[^>]*>\s*{re.escape(label)}\s*</h\1>"
    return len(re.findall(pattern, content))


class HandRolledEyebrowGuardTests(SimpleTestCase):
    """No eyebrow gets hand-rolled back into a converted template."""

    def test_converted_templates_use_the_atom(self):
        for path in (CHAT_TEMPLATE_PATH, ADMIN_TEMPLATE_PATH):
            with self.subTest(template=str(path)):
                self.assertNotRegex(path.read_text(), HANDROLLED_EYEBROW_RE)


@pytest.mark.postgres
class ChatPageEyebrowTests(TestCase):
    """Every chat-page eyebrow renders a heading at its declared level."""

    def test_developer_sees_every_eyebrow_heading(self):
        User = get_user_model()
        developer = User.objects.create_user(
            username="eyebrow_dev",
            email="eyebrow_dev@example.com",
            password="pw",
        )
        developer.groups.add(Group.objects.get(name=DEVELOPERS_GROUP))
        self.client.login(username="eyebrow_dev", password="pw")

        response = self.client.get(reverse("pages:chat"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Twice each: the desktop aside and the below-lg drawer.
        self.assertEqual(_heading_count(content, "Recent Activity", "2"), 2)
        self.assertEqual(_heading_count(content, "Briefcase", "2"), 2)
        self.assertEqual(_heading_count(content, "Your files", "4"), 1)


@pytest.mark.postgres
class AdminPageEyebrowTests(TestCase):
    """The admin panel eyebrow (icon, default level) renders as a heading."""

    def test_admin_sees_panel_eyebrow_heading(self):
        User = get_user_model()
        site_admin = User.objects.create_user(
            username="eyebrow_admin",
            email="eyebrow_admin@example.com",
            password="pw",
        )
        site_admin.groups.add(Group.objects.get(name=ADMINS_GROUP))
        self.client.login(username="eyebrow_admin", password="pw")

        response = self.client.get(reverse("pages:admin_dashboard"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertEqual(_heading_count(content, "Admin", "2"), 1)


@pytest.mark.postgres
class StyleGuideEyebrowTests(TestCase):
    """The style guide renders — it instantiates every component, so a
    renamed atom or a bad prop takes it down."""

    def test_eyebrow_demos_render(self):
        response = self.client.get(reverse("pages:style_guide"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertEqual(_heading_count(content, "Recent Activity"), 1)
        self.assertEqual(_heading_count(content, "No icon"), 1)
