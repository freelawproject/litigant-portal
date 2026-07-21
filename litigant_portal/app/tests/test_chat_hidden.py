"""Tests for hidden-message behavior in the chat_engine engine.

These pin the behavioral contract: hidden messages stay in the LLM history but
are excluded from every frontend projection, and injecting one doesn't disturb
the thread's ordering.
"""

import json

import pytest
from django.test import Client, TestCase

from litigant_portal.agents import WeatherAgent
from litigant_portal.app.models import ChatMessage, ChatThread, UserIdentity
from litigant_portal.app.selectors.chat_engine import chat_message_list
from litigant_portal.app.services.chat_engine import (
    _messages_for_llm,
    chat_message_inject_hidden,
    chat_message_inject_meta,
    thread_render_items,
)


@pytest.mark.postgres
class InjectHiddenMessageTests(TestCase):
    """chat_message_inject_hidden stores hidden=True without bumping the thread."""

    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="inject")
        self.thread = ChatThread.objects.create(identity=self.identity)

    def test_stores_hidden_message(self):
        message = chat_message_inject_hidden(
            thread_id=self.thread.id, content="context", model="gpt-5-mini"
        )
        self.assertTrue(message.hidden)
        self.assertEqual(message.data["role"], "user")
        self.assertEqual(message.data["content"], "context")

    def test_does_not_bump_thread_updated_at(self):
        before = ChatThread.objects.get(pk=self.thread.pk).updated_at
        chat_message_inject_hidden(
            thread_id=self.thread.id, content="context", model="gpt-5-mini"
        )
        after = ChatThread.objects.get(pk=self.thread.pk).updated_at
        self.assertEqual(after, before)


@pytest.mark.postgres
class InjectMetaMessageTests(TestCase):
    """chat_message_inject_meta stores an accounting-only meta message."""

    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="meta")
        self.thread = ChatThread.objects.create(identity=self.identity)

    def test_stores_meta_message(self):
        message = chat_message_inject_meta(
            thread_id=self.thread.id,
            kind="thread_description",
            model="gpt-5-mini",
            num_tokens=42,
            cost=0.001,
        )
        self.assertTrue(message.meta)
        self.assertEqual(message.data["role"], "meta")
        self.assertEqual(message.data["kind"], "thread_description")
        self.assertEqual(message.num_tokens, 42)
        self.assertEqual(message.cost, 0.001)

    def test_does_not_bump_thread_updated_at(self):
        before = ChatThread.objects.get(pk=self.thread.pk).updated_at
        chat_message_inject_meta(
            thread_id=self.thread.id, kind="test", model="gpt-5-mini"
        )
        after = ChatThread.objects.get(pk=self.thread.pk).updated_at
        self.assertEqual(after, before)


@pytest.mark.postgres
class ChatMessageListVisibilityTests(TestCase):
    """chat_message_list's flags carve out the three projections: everything
    (usage), minus meta (LLM history), minus hidden and meta (render)."""

    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="visibility")
        self.thread = ChatThread.objects.create(identity=self.identity)
        self.visible = ChatMessage.objects.create(
            thread=self.thread,
            data={"role": "user", "content": "shown"},
        )
        self.hidden = ChatMessage.objects.create(
            thread=self.thread,
            data={"role": "user", "content": "secret"},
            hidden=True,
        )
        self.meta = ChatMessage.objects.create(
            thread=self.thread,
            data={"role": "meta", "kind": "thread_description"},
            meta=True,
        )

    def ids(self, **flags):
        return set(
            chat_message_list(thread=self.thread, **flags).values_list(
                "id", flat=True
            )
        )

    def test_full_list_includes_everything(self):
        self.assertEqual(
            self.ids(), {self.visible.id, self.hidden.id, self.meta.id}
        )

    def test_llm_history_excludes_meta_only(self):
        self.assertEqual(
            self.ids(exclude_meta=True), {self.visible.id, self.hidden.id}
        )

    def test_render_view_excludes_hidden_and_meta(self):
        self.assertEqual(
            self.ids(exclude_hidden=True, exclude_meta=True),
            {self.visible.id},
        )


@pytest.mark.postgres
class HiddenMessageProjectionTests(TestCase):
    """A hidden message reaches the LLM but not the frontend projections."""

    def setUp(self):
        self.client = Client()
        # First request establishes a session + identity for the client.
        self.client.get("/api/agents/assistant/threads/")
        self.identity = UserIdentity.objects.get(
            session_key=self.client.session.session_key
        )
        self.thread = ChatThread.objects.create(
            identity=self.identity, thread_type="user_chat"
        )
        ChatMessage.objects.create(
            thread=self.thread,
            data={"role": "user", "content": "visible question"},
        )
        chat_message_inject_hidden(
            thread_id=self.thread.id,
            content="HIDDEN CONTEXT",
            model="gpt-5-mini",
        )

    def test_hidden_reaches_llm_history(self):
        history = [dict(m.data) for m in chat_message_list(thread=self.thread)]
        contents = [
            m["content"]
            for m in _messages_for_llm(
                "sys", history, model="gpt-5-mini", attachment_cache={}
            )
        ]
        self.assertIn("HIDDEN CONTEXT", contents)

    def test_hidden_excluded_from_render_items(self):
        items = thread_render_items(
            thread=self.thread, agent_class=WeatherAgent
        )
        contents = [item.get("content") for item in items]
        self.assertIn("visible question", contents)
        self.assertNotIn("HIDDEN CONTEXT", contents)

    def test_hidden_excluded_from_sidebar_snippet(self):
        data = json.loads(
            self.client.get("/api/agents/assistant/threads/").content
        )
        snippet = next(
            t["snippet"]
            for t in data["threads"]
            if t["id"] == str(self.thread.id)
        )
        self.assertEqual(snippet, "visible question")
