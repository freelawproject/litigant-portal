"""DB-free tests for the topic flow selectors that read a row without
querying: the URL kwargs a flow's guided page reverses from."""

from django.urls import reverse

from litigant_portal.app.models import Topic, TopicFlow
from litigant_portal.app.selectors.topic_flow import topic_flow_url_kwargs


def test_url_kwargs_reverse_to_the_flows_guided_page():
    flow = TopicFlow(
        topic=Topic(slug="eviction", court="franklin"), slug="tenant"
    )
    kwargs = topic_flow_url_kwargs(flow)
    assert kwargs == {
        "court": "franklin",
        "topic": "eviction",
        "role": "tenant",
    }
    assert (
        reverse("pages:topic_flow", kwargs=kwargs)
        == "/t/franklin/eviction/tenant/"
    )


def test_a_topic_without_a_court_has_no_url_kwargs():
    flow = TopicFlow(topic=Topic(slug="eviction", court=""), slug="tenant")
    assert topic_flow_url_kwargs(flow) is None
