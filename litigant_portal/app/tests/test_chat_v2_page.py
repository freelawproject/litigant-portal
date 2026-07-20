"""Discovery #670: the v2 chat page surfaces the guided-flow links."""

import pytest
from django.test import Client, TestCase
from django.urls import reverse

from litigant_portal.app.topic_flow.registry import registry


@pytest.mark.postgres
class ChatV2FlowTracksTests(TestCase):
    """The v2 chat view exposes the full track inventory (no topic context)."""

    def setUp(self):
        self.client = Client()

    def test_context_exposes_all_authored_tracks(self):
        response = self.client.get(reverse("pages:chat_v2"))
        assert response.status_code == 200
        tracks = response.context["flow_tracks"]
        # Topic-less surface gets the whole inventory, not a topic slice.
        assert tracks == registry.all_tracks()
        assert tracks, "repo corpus should yield at least one track"
        assert {"court", "topic", "role", "label", "title"} <= set(tracks[0])
