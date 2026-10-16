"""The guided page built from rows, against the real corpus.

One postgres test: sync ``litigant_portal/corpus/`` for real (no fake), then
render every enabled flow under ``TOPIC_FLOW_SOURCE=corpus``. A corpus change
the page cannot render fails here, in CI, rather than on a partner's instance.
The Python-built corpus tests live in ``test_topic_flow_rows_view.py``.
"""

import re

import pytest

from litigant_portal.app.selectors.corpus import corpus_load_topics
from litigant_portal.app.selectors.topic_flow import topic_flow_list
from litigant_portal.app.services.corpus import corpus_sync


def _expected_anchors(flow):
    """The layout with the interview block expanded to its pages."""
    anchors = []
    for name in flow.layout:
        if name == "interview":
            pages = flow.interview_pages.count()
            anchors += [f"interview-{n}" for n in range(1, pages + 1)]
        else:
            anchors.append(name)
    return anchors


@pytest.mark.postgres
def test_every_live_flow_renders_with_an_anchor_per_section_key(
    client, db, settings
):
    settings.TOPIC_FLOW_SOURCE = "corpus"
    settings.CORPUS_COURT = None
    corpus_sync(strict=True)
    court_of = {topic: court for court, topic in corpus_load_topics()}
    flows = topic_flow_list()
    assert flows

    for flow in flows:
        topic = flow.topic.slug
        url = f"/t/{court_of[topic]}/{topic}/{flow.slug}/"
        response = client.get(url)
        assert response.status_code == 200, url
        anchors = re.findall(
            r'<section id="([^"]+)"', response.content.decode()
        )
        assert anchors == _expected_anchors(flow), url
        assert set(flow.sections.values_list("key", flat=True)) <= set(
            anchors
        ), url
