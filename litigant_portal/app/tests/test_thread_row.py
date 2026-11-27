"""Rendered accessibility contracts for chat thread rows."""

from html.parser import HTMLParser

import pytest
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse


class AnchorParser(HTMLParser):
    """Collect anchor attributes from rendered template output."""

    def __init__(self):
        super().__init__()
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.anchors.append(dict(attrs))


@pytest.mark.postgres
class ChatSidebarThreadRowTests(TestCase):
    def test_chat_page_renders_a_keyboard_accessible_sidebar_link(self):
        response = self.client.get(reverse("pages:chat"))
        self.assertEqual(response.status_code, 200)
        chat_url = reverse("pages:chat")
        self.assertContains(response, f'data-chat-url="{chat_url}"')

        parser = AnchorParser()
        parser.feed(response.content.decode())
        rows = [
            anchor
            for anchor in parser.anchors
            if anchor.get("x-bind:href") == "thread.href"
        ]

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["x-on:click"], "selectThread")
        self.assertEqual(row["x-bind:data-thread-id"], "thread.id")
        self.assertEqual(row["x-bind:aria-current"], "thread.ariaCurrent")
        self.assertIn("focus-visible:outline-2", row["class"])
        self.assertIn("block", row["class"])

    def test_home_activity_link_renders_from_the_shared_molecule(self):
        content = render_to_string(
            "pages/chat/partials/_thread_list_static.html",
            {
                "activity_threads": [
                    {
                        "id": "abc",
                        "description": "A past chat",
                        "last_at": None,
                        "when": "2d ago",
                        "snippet": "hi",
                    }
                ]
            },
        )

        parser = AnchorParser()
        parser.feed(content)
        row = next(
            anchor
            for anchor in parser.anchors
            if anchor.get("href", "").endswith("?thread=abc")
        )
        self.assertIn("A past chat", content)
        self.assertIn("focus-visible:outline-2", row["class"])

    def test_style_guide_renders_the_shared_thread_row_with_focus_ring(self):
        content = render_to_string("pages/style_guide.html")
        parser = AnchorParser()
        parser.feed(content)

        row = next(
            anchor
            for anchor in parser.anchors
            if anchor.get("href") == "#thread-row"
            and "rounded-lg" in anchor.get("class", "")
        )
        self.assertIn("focus-visible:outline-2", row["class"])
