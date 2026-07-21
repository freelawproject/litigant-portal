"""chat === v2 (#676): the default chat surface is the v2 page."""

import pytest
from django.test import Client, TestCase
from django.urls import reverse


@pytest.mark.postgres
class ChatDefaultSurfaceTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_chat_serves_v2(self):
        response = self.client.get(reverse("pages:chat"))
        assert response.status_code == 200
        self.assertTemplateUsed(response, "v2/chat/index.html")

    def test_v1_query_params_are_ignored_not_fatal(self):
        # Deep links still carry ?topic=/?court=; v2 has no topic grounding
        # yet (#670 tests that condition), so they must be harmless.
        response = self.client.get(
            reverse("pages:chat"), {"topic": "eviction"}
        )
        assert response.status_code == 200
        self.assertTemplateUsed(response, "v2/chat/index.html")

    def test_v1_reference_url_still_serves(self):
        # Known-URL access to v1 for the UI/UX merge reference (#668).
        response = self.client.get(reverse("pages:chat_v1"))
        assert response.status_code == 200
        self.assertTemplateUsed(response, "pages/chat.html")
