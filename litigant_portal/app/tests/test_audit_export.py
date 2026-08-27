"""Tests for the audit transcript export functions."""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from litigant_portal.app.models import (
    ChatMessage,
    ChatThread,
    PromptArtifact,
    UserIdentity,
)
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

    def _artifact(
        self,
        *,
        system_prompt="Audit this prompt.",
        tool_schemas=None,
        hash_char="a",
    ):
        return PromptArtifact.objects.create(
            system_prompt=system_prompt,
            tool_schemas=[] if tool_schemas is None else tool_schemas,
            content_hash=hash_char * 64,
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

    def test_markdown_renders_first_artifact_without_repeating_it(self):
        artifact = self._artifact()
        self._message({"role": "user", "content": "Help me."})
        self._message(
            {"role": "assistant", "content": "First answer."},
            prompt_artifact=artifact,
        )
        self._message(
            {"role": "assistant", "content": "Second answer."},
            prompt_artifact=artifact,
        )

        markdown = chat_thread_export_markdown(thread=self.thread)

        self.assertEqual(markdown.count("## Prompt artifact"), 1)
        self.assertEqual(markdown.count(f"- ID: `{artifact.id}`"), 1)
        self.assertIn(f"- Content hash: `{artifact.content_hash}`", markdown)
        self.assertLess(
            markdown.index(f"- ID: `{artifact.id}`"),
            markdown.index("First answer."),
        )
        self.assertIn("```json\n[]\n```", markdown)

    def test_markdown_renders_changed_artifact(self):
        first = self._artifact(system_prompt="First prompt.")
        second = self._artifact(system_prompt="Second prompt.", hash_char="b")
        self._message(
            {"role": "assistant", "content": "First answer."},
            prompt_artifact=first,
        )
        self._message(
            {"role": "assistant", "content": "Second answer."},
            prompt_artifact=second,
        )

        markdown = chat_thread_export_markdown(thread=self.thread)

        self.assertEqual(markdown.count("## Prompt artifact"), 2)
        self.assertLess(
            markdown.index(f"- ID: `{first.id}`"),
            markdown.index(f"- ID: `{second.id}`"),
        )
        self.assertLess(
            markdown.index(f"- ID: `{second.id}`"),
            markdown.index("Second answer."),
        )

    def test_markdown_renders_artifact_again_when_returning_to_it(self):
        first = self._artifact(system_prompt="First prompt.")
        second = self._artifact(system_prompt="Second prompt.", hash_char="b")
        for content, artifact in (
            ("First answer.", first),
            ("Second answer.", second),
            ("Third answer.", first),
        ):
            self._message(
                {"role": "assistant", "content": content},
                prompt_artifact=artifact,
            )

        markdown = chat_thread_export_markdown(thread=self.thread)

        self.assertEqual(markdown.count("## Prompt artifact"), 3)
        self.assertEqual(markdown.count(f"- ID: `{first.id}`"), 2)
        second_first_id = markdown.index(f"- ID: `{second.id}`")
        returned_first_id = markdown.index(
            f"- ID: `{first.id}`", second_first_id
        )
        self.assertLess(returned_first_id, markdown.index("Third answer."))

    def test_markdown_null_rows_do_not_reset_active_artifact(self):
        artifact = self._artifact()
        self._message(
            {"role": "assistant", "content": "First answer."},
            prompt_artifact=artifact,
        )
        self._message({"role": "user", "content": "Follow-up."})
        self._message(
            {
                "role": "tool",
                "name": "lookup",
                "tool_call_id": "call-1",
                "content": "Tool result.",
            }
        )
        self._message({"role": "meta", "kind": "accounting"}, meta=True)
        self._message(
            {"role": "assistant", "content": "Second answer."},
            prompt_artifact=artifact,
        )

        markdown = chat_thread_export_markdown(thread=self.thread)

        self.assertEqual(markdown.count("## Prompt artifact"), 1)
        self.assertIn("Follow-up.", markdown)
        self.assertIn("Tool result.", markdown)
        self.assertIn("## meta: accounting [meta]", markdown)

    def test_markdown_legacy_null_assistant_messages_are_safe(self):
        artifact = self._artifact()
        self._message({"role": "assistant", "content": "Legacy before."})
        self._message(
            {"role": "assistant", "content": "Captured answer."},
            prompt_artifact=artifact,
        )
        self._message({"role": "assistant", "content": "Legacy between."})
        self._message(
            {"role": "assistant", "content": "Captured again."},
            prompt_artifact=artifact,
        )

        markdown = chat_thread_export_markdown(thread=self.thread)

        self.assertEqual(markdown.count("## Prompt artifact"), 1)
        self.assertLess(
            markdown.index("Legacy before."),
            markdown.index(f"- ID: `{artifact.id}`"),
        )
        self.assertIn("Legacy between.", markdown)

    def test_markdown_tool_call_only_assistant_renders_artifact(self):
        artifact = self._artifact()
        self._message(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "lookup",
                            "arguments": '{"query": "eviction"}',
                        },
                    }
                ],
            },
            prompt_artifact=artifact,
        )

        markdown = chat_thread_export_markdown(thread=self.thread)

        self.assertLess(
            markdown.index(f"- ID: `{artifact.id}`"),
            markdown.index('Tool call: lookup({"query": "eviction"})'),
        )

    def test_markdown_tool_schema_only_change_is_visible(self):
        first = self._artifact(
            system_prompt="Same prompt.",
            tool_schemas=[{"function": {"name": "first_tool"}}],
        )
        second = self._artifact(
            system_prompt="Same prompt.",
            tool_schemas=[{"function": {"name": "second_tool"}}],
            hash_char="b",
        )
        self._message(
            {"role": "assistant", "content": "First answer."},
            prompt_artifact=first,
        )
        self._message(
            {"role": "assistant", "content": "Second answer."},
            prompt_artifact=second,
        )

        markdown = chat_thread_export_markdown(thread=self.thread)

        self.assertEqual(markdown.count("## Prompt artifact"), 2)
        self.assertEqual(markdown.count("Same prompt."), 2)
        self.assertIn('"name": "first_tool"', markdown)
        self.assertIn('"name": "second_tool"', markdown)

    def test_markdown_contains_fences_and_orders_sha_before_prompt_change(
        self,
    ):
        embedded_markdown = "# Nested heading\n\n```python\nprint('safe')\n```"
        first = self._artifact(system_prompt="First prompt.")
        second = self._artifact(system_prompt=embedded_markdown, hash_char="b")
        self._message(
            {"role": "assistant", "content": "Before deploy."},
            prompt_artifact=first,
            git_sha="abc1234",
        )
        self._message(
            {"role": "assistant", "content": "After deploy."},
            prompt_artifact=second,
            git_sha="def5678",
        )

        markdown = chat_thread_export_markdown(thread=self.thread)

        self.assertIn(
            f"````text\n{embedded_markdown}\n````",
            markdown,
        )
        sha_change = markdown.index("**Deployed SHA changed to def5678**")
        prompt_change = markdown.index(f"- ID: `{second.id}`")
        assistant_message = markdown.index("After deploy.")
        self.assertLess(sha_change, prompt_change)
        self.assertLess(prompt_change, assistant_message)

    def test_json_export_defines_each_referenced_prompt_artifact_once(self):
        artifact = PromptArtifact.objects.create(
            system_prompt="Audit this exact prompt.",
            tool_schemas=[
                {"type": "function", "function": {"name": "lookup"}}
            ],
            content_hash="a" * 64,
        )
        user = self._message(
            {"role": "user", "content": "Help me."},
        )
        first = self._message(
            {"role": "assistant", "content": "First answer."},
            prompt_artifact=artifact,
        )
        second = self._message(
            {"role": "assistant", "content": "Second answer."},
            prompt_artifact=artifact,
        )

        export = chat_thread_export_data(thread=self.thread)

        self.assertEqual(
            export["prompt_artifacts"],
            [
                {
                    "id": str(artifact.id),
                    "content_hash": "a" * 64,
                    "system_prompt": "Audit this exact prompt.",
                    "tool_schemas": [
                        {"type": "function", "function": {"name": "lookup"}}
                    ],
                }
            ],
        )
        references = {
            message["id"]: message["prompt_artifact_id"]
            for message in export["messages"]
        }
        self.assertIsNone(references[str(user.id)])
        self.assertEqual(references[str(first.id)], str(artifact.id))
        self.assertEqual(references[str(second.id)], str(artifact.id))

    def test_json_export_includes_two_distinct_prompt_artifacts(self):
        first_artifact = PromptArtifact.objects.create(
            system_prompt="First rendered prompt.",
            tool_schemas=[],
            content_hash="b" * 64,
        )
        second_artifact = PromptArtifact.objects.create(
            system_prompt="Refreshed rendered prompt.",
            tool_schemas=[
                {"type": "function", "function": {"name": "lookup"}}
            ],
            content_hash="c" * 64,
        )
        first_assistant = self._message(
            {"role": "assistant", "content": "First answer."},
            prompt_artifact=first_artifact,
        )
        second_assistant = self._message(
            {"role": "assistant", "content": "Second answer."},
            prompt_artifact=second_artifact,
        )

        export = chat_thread_export_data(thread=self.thread)

        artifacts_by_id = {
            artifact["id"]: artifact for artifact in export["prompt_artifacts"]
        }
        self.assertEqual(len(export["prompt_artifacts"]), 2)
        self.assertEqual(
            set(artifacts_by_id),
            {str(first_artifact.id), str(second_artifact.id)},
        )
        self.assertEqual(
            artifacts_by_id[str(first_artifact.id)]["system_prompt"],
            "First rendered prompt.",
        )
        self.assertEqual(
            artifacts_by_id[str(second_artifact.id)]["system_prompt"],
            "Refreshed rendered prompt.",
        )

        references = {
            message["id"]: message["prompt_artifact_id"]
            for message in export["messages"]
        }
        self.assertEqual(
            references[str(first_assistant.id)], str(first_artifact.id)
        )
        self.assertEqual(
            references[str(second_assistant.id)], str(second_artifact.id)
        )

    def test_json_export_handles_legacy_null_prompt_artifact(self):
        legacy = self._message(
            {"role": "assistant", "content": "Pre-artifact answer."}
        )

        export = chat_thread_export_data(thread=self.thread)

        self.assertEqual(export["prompt_artifacts"], [])
        self.assertIsNone(export["messages"][0]["prompt_artifact_id"])
        self.assertEqual(export["messages"][0]["id"], str(legacy.id))
