"""Tests for ChatSession topic/jurisdiction persistence (#257).

Tests the full flow: new sessions persist topic/jurisdiction,
resumed sessions read them back and use them for prompt composition.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from litigant_portal.app.middleware import IdentityMiddleware
from litigant_portal.app.models import ChatSession, UserIdentity

User = get_user_model()


@pytest.mark.postgres
class ChatSessionTopicFieldTests(TestCase):
    """Tests for topic and jurisdiction fields on ChatSession."""

    def setUp(self):
        self.identity = UserIdentity.objects.create()

    def test_topic_defaults_to_empty(self):
        session = ChatSession.objects.create(identity=self.identity)

        self.assertEqual(session.topic, "")

    def test_jurisdiction_defaults_to_empty(self):
        session = ChatSession.objects.create(identity=self.identity)

        self.assertEqual(session.jurisdiction, "")

    def test_topic_persists(self):
        session = ChatSession.objects.create(
            identity=self.identity, topic="housing"
        )

        session.refresh_from_db()

        self.assertEqual(session.topic, "housing")

    def test_jurisdiction_persists(self):
        session = ChatSession.objects.create(
            identity=self.identity, jurisdiction="il"
        )

        session.refresh_from_db()

        self.assertEqual(session.jurisdiction, "il")

    def test_both_fields_persist_together(self):
        session = ChatSession.objects.create(
            identity=self.identity, topic="housing", jurisdiction="il"
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
        IdentityMiddleware(lambda r: None)(request)
        return request

    def test_new_session_persists_topic(self):
        """ChatService should save topic on the session when creating."""
        from litigant_portal.app.services.chat_service import ChatService

        request = self._make_request()
        chat = ChatService(request, topic="eviction")

        session = chat.agent.session
        session.refresh_from_db()

        self.assertEqual(session.topic, "eviction")

    def test_new_session_persists_jurisdiction(self):
        """ChatService should save jurisdiction on the session when creating."""
        from litigant_portal.app.services.chat_service import ChatService

        request = self._make_request()
        chat = ChatService(request, topic="eviction")

        session = chat.agent.session
        session.refresh_from_db()

        self.assertEqual(session.jurisdiction, "oh")

    def test_resumed_session_uses_stored_topic(self):
        """Resuming a session should use the stored topic, not require it again."""
        from litigant_portal.app.services.chat_service import ChatService

        request = self._make_request()
        # Create initial session with topic
        chat = ChatService(request, topic="eviction")
        session_id = chat.agent.session.id

        # Resume without passing topic
        chat2 = ChatService(request, session_id=session_id)

        self.assertEqual(chat2.agent.session.topic, "eviction")
        self.assertEqual(chat2.agent.session.jurisdiction, "oh")

    def test_no_topic_creates_generic_session(self):
        """Session without topic should have empty topic/jurisdiction."""
        from litigant_portal.app.services.chat_service import ChatService

        request = self._make_request()
        chat = ChatService(request)

        session = chat.agent.session
        session.refresh_from_db()

        self.assertEqual(session.topic, "")
        self.assertEqual(session.jurisdiction, "")

    def test_grid_eviction_slug_composes_topic_and_court_layers(self):
        """The grid slug for eviction must compose Topic + Court layers.

        Regression guard for #330: before this fix, the grid used "housing"
        as its slug but the prompt registry was keyed on "eviction", so
        clicking the topic card silently dropped the Topic + Court layers
        and users got BASE + Phase only. This test reads the grid's slug
        from TOPICS and asserts that passing it through ChatService yields
        a prompt with the eviction and Franklin anchors present.
        """
        from litigant_portal.app.services.chat_service import ChatService
        from litigant_portal.app.views import TOPICS

        eviction_slugs = [
            slug
            for slug, meta in TOPICS.items()
            if "Eviction" in str(meta.get("title", ""))
        ]
        self.assertEqual(
            len(eviction_slugs),
            1,
            f"Expected exactly one eviction tile in grid, found {eviction_slugs}",
        )
        grid_slug = eviction_slugs[0]

        request = self._make_request()
        chat = ChatService(request, topic=grid_slug)

        system_message = chat.agent.messages[0]
        self.assertEqual(system_message["role"], "system")
        prompt = system_message["content"]

        self.assertIn("EVICTION", prompt)
        self.assertIn("FRANKLIN COUNTY", prompt)

    def test_grid_name_change_slug_composes_topic_and_court_layers(self):
        """The grid slug for adult name change must compose Topic + Court layers.

        Companion to ``test_grid_eviction_slug_composes_topic_and_court_layers``
        (#330): reads the grid's name-change slug from TOPICS and asserts
        the composed prompt contains the adult-name-change and North Dakota
        anchors. Regression guard for #326.
        """
        from litigant_portal.app.services.chat_service import ChatService
        from litigant_portal.app.views import TOPICS

        name_change_slugs = [
            slug
            for slug, meta in TOPICS.items()
            if "Name Change" in str(meta.get("title", ""))
        ]
        self.assertEqual(
            len(name_change_slugs),
            1,
            f"Expected exactly one name-change tile in grid, found {name_change_slugs}",
        )
        grid_slug = name_change_slugs[0]

        request = self._make_request()
        chat = ChatService(request, topic=grid_slug)

        system_message = chat.agent.messages[0]
        self.assertEqual(system_message["role"], "system")
        prompt = system_message["content"]

        self.assertIn("ADULT NAME CHANGE", prompt)
        self.assertIn("NORTH DAKOTA", prompt)

    def test_explicit_court_kwarg_composes_court_layer(self):
        """ChatService accepts an explicit court kwarg (#327 deep-link path)."""
        from litigant_portal.app.services.chat_service import ChatService

        request = self._make_request()
        chat = ChatService(
            request, topic="adult_name_change", court="north-dakota"
        )

        prompt = chat.agent.messages[0]["content"]
        self.assertIn("ADULT NAME CHANGE", prompt)
        self.assertIn("NORTH DAKOTA", prompt)

        session = chat.agent.session
        session.refresh_from_db()
        self.assertEqual(session.topic, "adult_name_change")
        # Session still stores the two-letter jurisdiction (independent of the
        # canonical court slug used for prompt composition / deep-link URLs).
        self.assertEqual(session.jurisdiction, "nd")

    def test_explicit_court_wins_over_topic_default(self):
        """court kwarg overrides _DEFAULT_JURISDICTION_FOR_TOPIC mapping."""
        from litigant_portal.app.services.chat_service import ChatService

        request = self._make_request()
        # eviction's default jurisdiction is "oh" (→ franklin-county-oh court);
        # pass court=north-dakota to override and prove explicit court wins.
        chat = ChatService(request, topic="eviction", court="north-dakota")

        prompt = chat.agent.messages[0]["content"]
        self.assertIn("EVICTION", prompt)
        self.assertIn("NORTH DAKOTA", prompt)
        self.assertNotIn("FRANKLIN COUNTY", prompt)
