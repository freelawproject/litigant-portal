"""Thread-type scoping: one agent surface can never read another's threads."""

import json

import pytest
from django.test import Client, TestCase

from litigant_portal.app.models import ChatMessage, ChatThread, UserIdentity

BASE = "/api/agents/assistant/"


@pytest.mark.postgres
class ThreadTypeScopingTests(TestCase):
    def setUp(self):
        self.client = Client()
        # First request establishes a session + identity for the client.
        self.client.get(BASE + "threads/")
        self.identity = UserIdentity.objects.get(
            session_key=self.client.session.session_key
        )
        self.user_thread = ChatThread.objects.create(
            identity=self.identity, thread_type="user_chat"
        )
        # Same identity, different surface — must be invisible here.
        self.other_thread = ChatThread.objects.create(
            identity=self.identity, thread_type="admin_assistant"
        )
        ChatMessage.objects.create(
            thread=self.other_thread,
            data={"role": "user", "content": "admin-only content"},
        )

    def test_thread_list_only_returns_own_type(self):
        data = json.loads(self.client.get(BASE + "threads/").content)
        ids = {t["id"] for t in data["threads"]}
        self.assertIn(str(self.user_thread.id), ids)
        self.assertNotIn(str(self.other_thread.id), ids)

    def test_message_list_404s_for_other_type(self):
        res = self.client.get(f"{BASE}threads/{self.other_thread.id}/")
        self.assertEqual(res.status_code, 404)

    def test_delete_404s_for_other_type(self):
        res = self.client.post(f"{BASE}threads/{self.other_thread.id}/delete/")
        self.assertEqual(res.status_code, 404)
        self.assertTrue(
            ChatThread.objects.filter(id=self.other_thread.id).exists()
        )

    def test_stream_404s_for_other_type_thread(self):
        res = self.client.post(
            BASE + "stream/",
            {"message": "hi", "thread_id": str(self.other_thread.id)},
        )
        self.assertEqual(res.status_code, 404)
