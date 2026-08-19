"""Tests that chat_message_create stamps the deployed git SHA (#801)."""

import pytest
from django.test import TestCase, override_settings

from litigant_portal.app.models import ChatThread, UserIdentity
from litigant_portal.app.services.chat_engine import chat_message_create


@pytest.mark.postgres
class ChatMessageGitShaTests(TestCase):
    def setUp(self):
        self.identity = UserIdentity.objects.create(session_key="git-sha")
        self.thread = ChatThread.objects.create(identity=self.identity)

    @override_settings(GIT_SHA="abc1234")
    def test_stamps_current_git_sha(self):
        message = chat_message_create(
            thread_id=self.thread.id,
            data={"role": "user", "content": "hello"},
            model="gpt-5-mini",
        )
        self.assertEqual(message.git_sha, "abc1234")

    @override_settings(GIT_SHA="def5678")
    def test_restamps_when_setting_changes_mid_thread(self):
        first = chat_message_create(
            thread_id=self.thread.id,
            data={"role": "user", "content": "first"},
            model="gpt-5-mini",
        )
        with override_settings(GIT_SHA="ghi9012"):
            second = chat_message_create(
                thread_id=self.thread.id,
                data={"role": "assistant", "content": "second"},
                model="gpt-5-mini",
            )
        self.assertEqual(first.git_sha, "def5678")
        self.assertEqual(second.git_sha, "ghi9012")

    def test_defaults_to_empty_string_for_directly_created_rows(self):
        message = self.thread.messages.create(
            data={"role": "user", "content": "legacy row"}
        )
        self.assertEqual(message.git_sha, "")
