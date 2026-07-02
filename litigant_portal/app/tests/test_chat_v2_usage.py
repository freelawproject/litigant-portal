"""Tests for token counting and cost tracking in the chat_v2 engine.

These pin the bookkeeping contract: chat_message_create trusts caller-supplied
counts (an assistant turn passes usage.completion_tokens) and otherwise counts
the message content itself, and chat_thread_usage sums tokens and cost across the
whole thread, hidden messages included.
"""

import pytest
from django.test import TestCase

from litigant_portal.app.models import ChatThread, UserIdentity
from litigant_portal.app.selectors.chat_v2 import chat_thread_usage
from litigant_portal.app.services.chat_v2 import (
    chat_message_create,
    chat_message_inject_hidden,
)

MODEL = "gpt-5-mini"


@pytest.mark.postgres
class ChatMessageCreateTests(TestCase):
    """chat_message_create — when it counts vs. when it trusts the caller."""

    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="usage-create")
        self.thread = ChatThread.objects.create(identity=self.identity)

    def test_uses_caller_supplied_counts_verbatim(self):
        # Assistant turns pass exact usage values; we store them, never recount.
        # The trivial content would count to ~1 token, proving no recount.
        message = chat_message_create(
            thread_id=self.thread.id,
            data={"role": "assistant", "content": "hi"},
            model=MODEL,
            num_tokens=4321,
            cost=0.0123,
        )
        self.assertEqual(message.num_tokens, 4321)
        self.assertAlmostEqual(message.cost, 0.0123)

    def test_counts_content_when_tokens_omitted(self):
        # Input messages (user/tool/injected) have no usage, so we count content.
        message = chat_message_create(
            thread_id=self.thread.id,
            data={"role": "user", "content": "How many tokens is this?"},
            model=MODEL,
        )
        self.assertGreater(message.num_tokens, 0)
        self.assertEqual(message.cost, 0.0)

    def test_explicit_zero_is_respected_not_recounted(self):
        # The guard is `num_tokens is None`, not a falsy check — an explicit 0
        # must be stored as-is even though the content would count above zero.
        message = chat_message_create(
            thread_id=self.thread.id,
            data={"role": "assistant", "content": "non-empty body"},
            model=MODEL,
            num_tokens=0,
        )
        self.assertEqual(message.num_tokens, 0)


@pytest.mark.postgres
class ChatThreadUsageTests(TestCase):
    """chat_thread_usage — totals across the thread, hidden messages included."""

    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="usage-sum")
        self.thread = ChatThread.objects.create(identity=self.identity)

    def test_empty_thread_totals_zero(self):
        self.assertEqual(
            chat_thread_usage(thread=self.thread),
            {"total_tokens": 0, "total_cost": 0.0},
        )

    def test_sums_tokens_and_cost(self):
        chat_message_create(
            thread_id=self.thread.id,
            data={"role": "user", "content": "q"},
            model=MODEL,
            num_tokens=10,
            cost=0.0,
        )
        chat_message_create(
            thread_id=self.thread.id,
            data={"role": "assistant", "content": "a"},
            model=MODEL,
            num_tokens=25,
            cost=0.005,
        )
        usage = chat_thread_usage(thread=self.thread)
        self.assertEqual(usage["total_tokens"], 35)
        self.assertAlmostEqual(usage["total_cost"], 0.005)

    def test_includes_hidden_messages(self):
        chat_message_create(
            thread_id=self.thread.id,
            data={"role": "user", "content": "visible"},
            model=MODEL,
            num_tokens=10,
        )
        hidden = chat_message_inject_hidden(
            thread_id=self.thread.id, content="hidden context", model=MODEL
        )
        self.assertGreater(hidden.num_tokens, 0)
        usage = chat_thread_usage(thread=self.thread)
        self.assertEqual(usage["total_tokens"], 10 + hidden.num_tokens)
