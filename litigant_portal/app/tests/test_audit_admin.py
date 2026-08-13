"""Tests for the read-only audit transcript surface in the Django admin."""

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from litigant_portal.app.models import ChatMessage, ChatThread, UserIdentity
from litigant_portal.app.tests.utils import SESSION_KEY, SHORT_KEY

User = get_user_model()


@pytest.mark.postgres
class AuditAdminTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.staff = User.objects.create_user(
            username="staff", password="pw", is_staff=True
        )
        self.identity = UserIdentity.objects.create(session_key=SESSION_KEY)
        self.thread = ChatThread.objects.create(
            identity=self.identity, description="Eviction help"
        )
        ChatMessage.objects.create(
            thread=self.thread,
            data={"role": "user", "content": "I got an eviction notice"},
        )
        ChatMessage.objects.create(
            thread=self.thread,
            data={
                "role": "assistant",
                "content": "Let me look that up.",
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
            },
        )
        ChatMessage.objects.create(
            thread=self.thread,
            data={
                "role": "tool",
                "tool_call_id": "call-1",
                "name": "search_topics",
                "content": "Found the housing topic.",
                "data": {},
            },
        )
        ChatMessage.objects.create(
            thread=self.thread,
            data={"role": "user", "content": "injected context"},
            hidden=True,
        )
        self.base_url = f"/django-admin/app/chatthread/{self.thread.pk}"
        self.client.login(username="staff", password="pw")

    def test_admin_index_links_to_chat_threads_for_bare_staff(self):
        response = self.client.get("/django-admin/")
        self.assertContains(response, "/django-admin/app/chatthread/")

    def test_changelist_lists_thread_with_truncated_owner(self):
        response = self.client.get("/django-admin/app/chatthread/")
        self.assertContains(response, "Eviction help")
        self.assertContains(response, f"anonymous (session {SHORT_KEY})")
        self.assertNotContains(response, SESSION_KEY)

    def test_view_page_renders_full_transcript(self):
        response = self.client.get(f"{self.base_url}/change/")
        self.assertContains(response, "I got an eviction notice")
        self.assertContains(response, "Tool call: search_topics")
        self.assertContains(response, "Found the housing topic.")
        self.assertContains(response, "[hidden]")
        self.assertContains(response, "injected context")
        self.assertContains(response, f"anonymous (session {SHORT_KEY})")
        self.assertNotContains(response, SESSION_KEY)

    def test_search_finds_threads_by_email_and_full_session_key(self):
        """Staff who already hold a key can still paste the whole thing in,
        even though no surface renders it."""
        owner = User.objects.create_user(
            username="litigant", email="litigant@example.com", password="pw"
        )
        ChatThread.objects.create(
            identity=UserIdentity.objects.create(user=owner),
            description="Account holder thread",
        )
        changelist = "/django-admin/app/chatthread/"

        by_email = self.client.get(changelist, {"q": "litigant@example.com"})
        self.assertContains(by_email, "Account holder thread")
        self.assertNotContains(by_email, "Eviction help")

        by_session = self.client.get(changelist, {"q": SESSION_KEY})
        self.assertContains(by_session, "Eviction help")
        self.assertNotContains(by_session, "Account holder thread")

    def test_search_finds_thread_by_uuid(self):
        response = self.client.get(
            "/django-admin/app/chatthread/", {"q": str(self.thread.pk)}
        )
        self.assertContains(response, "Eviction help")

    def test_markdown_download(self):
        response = self.client.get(f"{self.base_url}/transcript.md")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        content = response.content.decode()
        self.assertIn(f"anonymous (session {SHORT_KEY})", content)
        self.assertNotIn(SESSION_KEY, content)
        self.assertIn("Tool call: search_topics", content)
        self.assertIn("[hidden]", content)

    def test_json_download_is_full_fidelity(self):
        response = self.client.get(f"{self.base_url}/transcript.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response["Content-Disposition"])
        export = json.loads(response.content)
        self.assertEqual(export["thread_id"], str(self.thread.pk))
        self.assertEqual(export["owner"]["session_key"], SHORT_KEY)
        self.assertEqual(export["owner"]["identity_id"], str(self.identity.id))
        self.assertNotIn(SESSION_KEY, response.content.decode())
        roles = [m["data"]["role"] for m in export["messages"]]
        self.assertEqual(roles, ["user", "assistant", "tool", "user"])
        self.assertTrue(export["messages"][3]["hidden"])
        self.assertTrue(all("created_at" in m for m in export["messages"]))
        tool_calls = export["messages"][1]["data"]["tool_calls"]
        self.assertEqual(tool_calls[0]["function"]["name"], "search_topics")

    def test_json_download_keeps_non_ascii_text_readable(self):
        ChatMessage.objects.create(
            thread=self.thread,
            data={"role": "user", "content": "¿Cómo respondo al desalojo?"},
        )
        response = self.client.get(f"{self.base_url}/transcript.json")
        self.assertIn("¿Cómo respondo al desalojo?", response.content.decode())

    def test_thread_is_read_only(self):
        response = self.client.post(
            f"{self.base_url}/change/", {"description": "edited"}
        )
        self.assertEqual(response.status_code, 403)
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.description, "Eviction help")

    def test_non_staff_is_rejected(self):
        User.objects.create_user(username="litigant", password="pw")
        self.client.logout()
        self.client.login(username="litigant", password="pw")
        for url in [
            "/django-admin/app/chatthread/",
            f"{self.base_url}/transcript.md",
            f"{self.base_url}/transcript.json",
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/django-admin/login/", response["Location"])


@pytest.mark.postgres
class UserIdentityAdminTests(TestCase):
    """UserIdentityAdmin keeps Django's per-model permissions, so these need a
    superuser rather than the bare staff account the transcript surface uses."""

    def setUp(self):
        self.client = Client()
        User.objects.create_superuser(username="root", password="pw")
        self.client.login(username="root", password="pw")
        self.identity = UserIdentity.objects.create(session_key=SESSION_KEY)

    def test_changelist_truncates_the_session_key(self):
        response = self.client.get("/django-admin/app/useridentity/")
        self.assertContains(response, SHORT_KEY)
        self.assertNotContains(response, SESSION_KEY)

    def test_change_form_neither_renders_nor_edits_the_session_key(self):
        response = self.client.get(
            f"/django-admin/app/useridentity/{self.identity.id}/change/"
        )
        self.assertContains(response, SHORT_KEY)
        self.assertNotContains(response, SESSION_KEY)
        self.assertNotContains(response, 'name="session_key"')

    def test_changelist_still_finds_an_identity_by_full_session_key(self):
        response = self.client.get(
            "/django-admin/app/useridentity/", {"q": SESSION_KEY}
        )
        self.assertContains(response, str(self.identity.id))
