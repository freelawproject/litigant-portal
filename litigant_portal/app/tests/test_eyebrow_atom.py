"""Tests for the c-atoms.eyebrow atom.

Cotton tags compile only through django_cotton's loader, so these exercise the
atom through the pages that use it rather than in isolation. Between them the
chat page and the style guide cover every prop: with an icon and without,
level 2 and level 4.
"""

import re
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

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

    def test_superuser_sees_every_eyebrow_heading(self):
        User = get_user_model()
        User.objects.create_superuser(
            username="eyebrow_root",
            email="eyebrow_root@example.com",
            password="pw",
        )
        self.client.login(username="eyebrow_root", password="pw")

        response = self.client.get(reverse("pages:chat"))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # Twice each: the desktop aside and the below-lg drawer.
        self.assertEqual(_heading_count(content, "Recent Activity", "2"), 2)
        self.assertEqual(_heading_count(content, "Briefcase", "2"), 2)
        self.assertEqual(_heading_count(content, "Your files", "4"), 1)


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
