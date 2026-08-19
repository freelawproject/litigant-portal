"""Tests for the audit transcript export functions."""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from litigant_portal.app.models import ChatMessage, ChatThread, UserIdentity
from litigant_portal.app.selectors.chat_engine import (
    chat_thread_export_data,
    chat_thread_export_markdown,
    chat_thread_owner_label,
)
from litigant_portal.app.tests.utils import SESSION_KEY, SHORT_KEY

User = get_user_model()


@pytest.mark.postgres
class ThreadOwnerLabelTests(TestCase):
    def _thread_for(self, identity):
        return ChatThread.objects.create(identity=identity)

    def test_uses_email_for_a_logged_in_owner(self):
        user = User.objects.create_user(
            username="litigant", email="litigant@example.com", password="pw"
        )
        thread = self._thread_for(UserIdentity.objects.create(user=user))
        self.assertEqual(
            chat_thread_owner_label(thread=thread), "litigant@example.com"
        )

    def test_falls_back_to_username_when_email_is_blank(self):
        user = User.objects.create_user(username="no-email", password="pw")
        thread = self._thread_for(UserIdentity.objects.create(user=user))
        self.assertEqual(chat_thread_owner_label(thread=thread), "no-email")

    def test_labels_an_anonymous_owner_by_truncated_session_key(self):
        identity = UserIdentity.objects.create(session_key=SESSION_KEY)
        thread = self._thread_for(identity)
        label = chat_thread_owner_label(thread=thread)
        self.assertEqual(label, f"anonymous (session {SHORT_KEY})")
        self.assertNotIn(SESSION_KEY, label)


@pytest.mark.postgres
class ThreadExportTests(TestCase):
    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key=SESSION_KEY)
        self.thread = ChatThread.objects.create(
            identity=self.identity, description="Eviction help"
        )

    def _message(self, data, **kwargs):
        return ChatMessage.objects.create(
            thread=self.thread, data=data, **kwargs
        )

    def test_markdown_renders_meta_rows_with_accounting(self):
        self._message(
            {"role": "meta", "kind": "thread_description"},
            meta=True,
            num_tokens=42,
            cost=0.0007,
        )
        markdown = chat_thread_export_markdown(thread=self.thread)
        self.assertIn("## meta: thread_description [meta]", markdown)
        self.assertIn("(accounting only: 42 tokens, cost 0.0007)", markdown)

    def test_markdown_lists_user_attachments(self):
        self._message(
            {
                "role": "user",
                "content": "here is my notice",
                "attachments": ["notice.pdf", "lease.pdf"],
            }
        )
        markdown = chat_thread_export_markdown(thread=self.thread)
        self.assertIn("Attachments: notice.pdf, lease.pdf", markdown)

    def test_markdown_renders_a_tool_call_with_empty_content(self):
        self._message(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "search_topics",
                            "arguments": '{"query": "eviction"}',
                        },
                    }
                ],
            }
        )
        markdown = chat_thread_export_markdown(thread=self.thread)
        self.assertIn("## assistant (", markdown)
        self.assertIn(
            'Tool call: search_topics({"query": "eviction"})', markdown
        )

    def test_markdown_names_the_tool_behind_a_result_row(self):
        self._message(
            {
                "role": "tool",
                "tool_call_id": "call-1",
                "name": "search_topics",
                "content": "Found the housing topic.",
                "data": {},
            }
        )
        markdown = chat_thread_export_markdown(thread=self.thread)
        self.assertIn("## tool result: search_topics", markdown)

    def test_export_carries_thread_timestamps(self):
        export = chat_thread_export_data(thread=self.thread)
        self.assertEqual(
            export["created_at"], self.thread.created_at.isoformat()
        )
        self.assertEqual(
            export["updated_at"], self.thread.updated_at.isoformat()
        )

    def test_markdown_owner_line_truncates_the_session_key(self):
        markdown = chat_thread_export_markdown(thread=self.thread)
        self.assertIn(f"- Owner: anonymous (session {SHORT_KEY})", markdown)
        self.assertNotIn(SESSION_KEY, markdown)

    def test_json_owner_truncates_the_session_key(self):
        owner = chat_thread_export_data(thread=self.thread)["owner"]
        self.assertEqual(owner["session_key"], SHORT_KEY)

    def test_json_owner_carries_the_identity_id(self):
        """The truncated key is a hint; the identity id is the real handle for
        correlating several threads to one visitor."""
        owner = chat_thread_export_data(thread=self.thread)["owner"]
        self.assertEqual(owner["identity_id"], str(self.identity.id))

    def test_json_owner_carries_username_when_email_is_blank(self):
        user = User.objects.create_user(username="no-email", password="pw")
        thread = ChatThread.objects.create(
            identity=UserIdentity.objects.create(user=user)
        )
        owner = chat_thread_export_data(thread=thread)["owner"]
        self.assertEqual(owner["user_email"], "")
        self.assertEqual(owner["username"], "no-email")

    def test_json_export_carries_token_and_cost_fields(self):
        self._message(
            {"role": "assistant", "content": "Here is what to do."},
            num_tokens=120,
            cost=0.0031,
        )
        message = chat_thread_export_data(thread=self.thread)["messages"][0]
        self.assertEqual(message["num_tokens"], 120)
        self.assertEqual(message["cost"], 0.0031)
        self.assertFalse(message["hidden"])
        self.assertFalse(message["meta"])

    def test_json_export_carries_git_sha_per_message(self):
        self._message({"role": "user", "content": "hi"}, git_sha="abc1234")
        message = chat_thread_export_data(thread=self.thread)["messages"][0]
        self.assertEqual(message["git_sha"], "abc1234")

    def test_markdown_shows_deployed_sha_header(self):
        self._message({"role": "user", "content": "hi"}, git_sha="abc1234")
        markdown = chat_thread_export_markdown(thread=self.thread)
        self.assertIn("- Deployed SHA: abc1234", markdown)

    def test_markdown_header_falls_back_to_unknown_for_blank_sha(self):
        self._message({"role": "user", "content": "hi"}, git_sha="")
        markdown = chat_thread_export_markdown(thread=self.thread)
        self.assertIn("- Deployed SHA: unknown", markdown)

    def test_markdown_flags_a_sha_change_mid_thread(self):
        self._message({"role": "user", "content": "before"}, git_sha="abc1234")
        self._message(
            {"role": "assistant", "content": "after"}, git_sha="def5678"
        )
        markdown = chat_thread_export_markdown(thread=self.thread)
        self.assertIn("**Deployed SHA changed to def5678**", markdown)
        # Only the change is flagged, not the initial SHA already in the header.
        self.assertNotIn("changed to abc1234", markdown)
