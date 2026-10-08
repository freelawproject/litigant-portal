"""
Tests for the site frame (#988): the sticky header with its site menu, and
the left / content / right regions that chat, home and the topic flow share.
"""

import re

import pytest
from django.test import TestCase, override_settings
from django.urls import reverse

# The header's drawer buttons point at the frame's two regions by id.
LEFT_DRAWER_BUTTON = 'popovertarget="frame-left"'
RIGHT_DRAWER_BUTTON = 'popovertarget="frame-right"'
# The dev-only group's "Start over" control calls this devMenu method.
DEV_GROUP_MARKER = 'x-on:click="resetDemo"'
TOPIC_FLOW_KWARGS = {
    "court": "franklin-county-oh",
    "topic": "eviction",
    "role": "tenant",
}


def _left_region(html):
    """The markup of the frame's left region."""
    match = re.search(r'<aside id="frame-left".*?</aside>', html, re.S)
    assert match, "page has no left region"
    return match.group(0)


@pytest.mark.postgres
class FramedPagesTests(TestCase):
    def test_home_and_topic_flow_pass_the_briefcase_like_chat(self):
        """The briefcase is the right region on every framed page, so each
        view hands it the visitor's answers, wherever they were saved."""
        for url in (
            reverse("pages:home"),
            reverse("pages:topic_flow", kwargs=TOPIC_FLOW_KWARGS),
            reverse("pages:chat"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn("briefcase_groups", response.context)

    def test_topic_flow_left_region_jumps_to_each_section(self):
        """On a flow page the left region holds the flow's sections."""
        response = self.client.get(
            reverse("pages:topic_flow", kwargs=TOPIC_FLOW_KWARGS)
        )
        left = _left_region(response.content.decode())

        self.assertTrue(response.context["toc"])
        for item in response.context["toc"]:
            self.assertIn(f'href="#{item["anchor"]}"', left)

    def test_framed_pages_get_drawer_buttons_and_others_do_not(self):
        for url in (reverse("pages:home"), reverse("pages:chat")):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn(LEFT_DRAWER_BUTTON, html)
                self.assertIn(RIGHT_DRAWER_BUTTON, html)

        about = self.client.get(reverse("pages:about")).content.decode()
        self.assertNotIn(LEFT_DRAWER_BUTTON, about)
        self.assertNotIn(RIGHT_DRAWER_BUTTON, about)


@pytest.mark.postgres
class SiteMenuTests(TestCase):
    """The footer is gone, so its links live in the header's site menu, in
    every environment. Dev tools join them only outside production."""

    PAGE_LINKS = ("pages:about", "pages:privacy", "pages:accessibility")
    FREE_LAW_LINK = 'href="https://free.law"'

    @override_settings(DEPLOYMENT_ENV="prod")
    def test_production_menu_has_the_page_links_and_no_dev_tools(self):
        html = self.client.get(reverse("pages:home")).content.decode()

        for name in self.PAGE_LINKS:
            self.assertIn(f'href="{reverse(name)}"', html)
        self.assertIn(self.FREE_LAW_LINK, html)
        self.assertNotIn(DEV_GROUP_MARKER, html)

    @override_settings(DEPLOYMENT_ENV="dev")
    def test_dev_menu_adds_dev_tools_to_the_page_links(self):
        html = self.client.get(reverse("pages:home")).content.decode()

        for name in self.PAGE_LINKS:
            self.assertIn(f'href="{reverse(name)}"', html)
        self.assertIn(DEV_GROUP_MARKER, html)
