"""Tests for ChatSession topic/jurisdiction persistence (#257).

Tests the full flow: new sessions persist topic/jurisdiction,
resumed sessions read them back and use them for prompt composition.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from chat.models import ChatSession

User = get_user_model()


@pytest.mark.postgres
class ChatSessionTopicFieldTests(TestCase):
    """Tests for topic and jurisdiction fields on ChatSession."""

    def test_topic_defaults_to_empty(self):
        session = ChatSession.objects.create()

        self.assertEqual(session.topic, "")

    def test_jurisdiction_defaults_to_empty(self):
        session = ChatSession.objects.create()

        self.assertEqual(session.jurisdiction, "")

    def test_topic_persists(self):
        session = ChatSession.objects.create(topic="housing")

        session.refresh_from_db()

        self.assertEqual(session.topic, "housing")

    def test_jurisdiction_persists(self):
        session = ChatSession.objects.create(jurisdiction="il")

        session.refresh_from_db()

        self.assertEqual(session.jurisdiction, "il")

    def test_both_fields_persist_together(self):
        session = ChatSession.objects.create(
            topic="housing", jurisdiction="il"
        )

        session.refresh_from_db()

        self.assertEqual(session.topic, "housing")
        self.assertEqual(session.jurisdiction, "il")


@pytest.mark.postgres
class ChatSessionTopicServiceTests(TestCase):
    """Tests for topic/jurisdiction flow through ChatService."""

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username="testuser", password="testpass"
        )

    def _make_request(self):
        request = self.factory.post("/chat/stream/")
        request.user = self.user
        request.session = self.client.session
        request.session.create()
        return request

    def test_new_session_persists_topic(self):
        """ChatService should save topic on the session when creating."""
        from chat.services.chat_service import ChatService

        request = self._make_request()
        chat = ChatService(request, topic="housing")

        session = chat.agent.session
        session.refresh_from_db()

        self.assertEqual(session.topic, "housing")

    def test_new_session_persists_jurisdiction(self):
        """ChatService should save jurisdiction on the session when creating."""
        from chat.services.chat_service import ChatService

        request = self._make_request()
        chat = ChatService(request, topic="housing")

        session = chat.agent.session
        session.refresh_from_db()

        self.assertEqual(session.jurisdiction, "il")

    def test_resumed_session_uses_stored_topic(self):
        """Resuming a session should use the stored topic, not require it again."""
        from chat.services.chat_service import ChatService

        request = self._make_request()
        # Create initial session with topic
        chat = ChatService(request, topic="housing")
        session_id = chat.agent.session.id

        # Resume without passing topic
        chat2 = ChatService(request, session_id=session_id)

        self.assertEqual(chat2.agent.session.topic, "housing")
        self.assertEqual(chat2.agent.session.jurisdiction, "il")

    def test_no_topic_creates_generic_session(self):
        """Session without topic should have empty topic/jurisdiction."""
        from chat.services.chat_service import ChatService

        request = self._make_request()
        chat = ChatService(request)

        session = chat.agent.session
        session.refresh_from_db()

        self.assertEqual(session.topic, "")
        self.assertEqual(session.jurisdiction, "")
