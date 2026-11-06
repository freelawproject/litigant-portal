"""The chat sidebar's thread rows are real links (#1122).

A row that is only a click-handling <div> can't be tabbed to or opened from
the keyboard, and screen readers don't announce it as actionable. The sidebar
row must render as an anchor whose href is bound per thread, so Tab reaches it
and Enter opens it. selectThread then intercepts plain clicks to switch threads
in place, and leaves modified clicks to the browser.
"""

import re
from pathlib import Path

from django.template.loader import render_to_string
from django.test import SimpleTestCase

SIDEBAR_ROW_LINK_RE = re.compile(r'<a\b[^>]*\bx-bind:href="thread\.href"')
SIDEBAR_ROW_CLICK_RE = re.compile(
    r'<a\b(?=[^>]*\bx-on:click="selectThread")(?=[^>]*\bx-bind:data-thread-id="thread\.id")'
)
HOME_ROW_LINK_RE = re.compile(r'<a\b[^>]*\bhref="[^"]*\?thread=abc"')
FOCUS_RING_RE = re.compile(r"focus-visible:outline-2\b")
SELECT_THREAD_RE = re.compile(r"selectThread\(e\)\s*\{(.*?)\n {4}\}", re.DOTALL)

CHAT_ENGINE_JS = (
    Path(__file__).resolve().parents[1] / "static" / "js" / "chat_engine.js"
)


class ChatSidebarThreadRowTests(SimpleTestCase):
    def test_sidebar_thread_row_is_a_link(self):
        content = render_to_string("pages/chat/partials/_thread_list.html")

        self.assertRegex(content, SIDEBAR_ROW_LINK_RE)
        self.assertRegex(content, SIDEBAR_ROW_CLICK_RE)

    def test_select_thread_intercepts_plain_clicks_only(self):
        source = CHAT_ENGINE_JS.read_text(encoding="utf-8")
        match = SELECT_THREAD_RE.search(source)
        self.assertIsNotNone(match, "selectThread(e) not found in chat_engine.js")
        body = match.group(1)

        self.assertIn("e.preventDefault()", body)
        self.assertIn("e.button !== 0", body)
        for modifier in ("metaKey", "ctrlKey", "shiftKey", "altKey"):
            self.assertIn(modifier, body)

    def test_home_activity_row_is_a_link(self):
        content = render_to_string(
            "pages/chat/partials/_thread_list_static.html",
            {
                "activity_threads": [
                    {
                        "id": "abc",
                        "description": "",
                        "last_at": None,
                        "when": "2d ago",
                        "snippet": "hi",
                    }
                ]
            },
        )

        self.assertRegex(content, HOME_ROW_LINK_RE)

    def test_thread_row_has_visible_focus_ring(self):
        molecule = (
            Path(__file__).resolve().parents[1]
            / "templates"
            / "cotton"
            / "molecules"
            / "thread_row.html"
        ).read_text(encoding="utf-8")

        self.assertRegex(molecule, FOCUS_RING_RE)
