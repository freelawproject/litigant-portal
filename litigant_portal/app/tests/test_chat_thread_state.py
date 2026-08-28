"""chat_thread_state_merge is the single locked write path for thread
state."""

import pytest
from django.test import TestCase

from litigant_portal.app.models import ChatThread, UserIdentity
from litigant_portal.app.services.chat_engine import chat_thread_state_merge


@pytest.mark.postgres
class ChatThreadStateMergeTests(TestCase):
    def setUp(self):
        identity = UserIdentity.objects.create(session_key="merge")
        self.thread = ChatThread.objects.create(
            identity=identity, thread_type="user_chat", state={"kept": 1}
        )

    def test_merges_and_preserves_other_keys(self):
        merged = chat_thread_state_merge(
            thread_id=self.thread.id, updates={"added": 2}
        )
        self.assertEqual(merged, {"kept": 1, "added": 2})
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.state, {"kept": 1, "added": 2})

    def test_callable_updates_see_the_current_state(self):
        merged = chat_thread_state_merge(
            thread_id=self.thread.id,
            updates=lambda state: {"kept": state["kept"] + 1},
        )
        self.assertEqual(merged["kept"], 2)

    def test_callable_returning_empty_skips_the_write(self):
        before = self.thread.updated_at
        merged = chat_thread_state_merge(
            thread_id=self.thread.id, updates=lambda state: {}
        )
        self.assertEqual(merged, {"kept": 1})
        self.thread.refresh_from_db()
        self.assertEqual(self.thread.updated_at, before)
