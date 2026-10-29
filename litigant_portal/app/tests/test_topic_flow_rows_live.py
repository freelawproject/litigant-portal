"""The guided page built from rows, against the real corpus.

Postgres tests that sync ``litigant_portal/corpus/`` for real (no fake).
The first renders every enabled flow and saves one North Dakota page through
real glossary rows, so a corpus change the page cannot render fails here, in
CI, rather than on a partner's instance. The second builds the ND calendar
and contacts files (#1017). The Python-built corpus tests live in
``test_topic_flow_rows_view.py``.
"""

import re

import pytest

from litigant_portal.app.models import UserIdentity, Variable, VariableAnswer
from litigant_portal.app.selectors.corpus import corpus_load_topics
from litigant_portal.app.selectors.topic_flow import topic_flow_list
from litigant_portal.app.services.corpus import corpus_sync
from litigant_portal.app.services.topic_flow import variable_answer_set


def _expected_anchors(flow):
    """The layout with the interview block expanded to its marked pages."""
    anchors = []
    for name in flow.layout:
        if name == "interview":
            pages = flow.interview_pages.filter(on_page=True).count()
            anchors += [f"interview-{n}" for n in range(1, pages + 1)]
        else:
            anchors.append(name)
    return anchors


@pytest.mark.postgres
def test_every_live_flow_renders_with_an_anchor_per_section_key(
    client, db, settings
):
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

    # Save the "The filing fee" page of the ND standard flow: one boolean
    # the packet reacts to. The anchor is not hard-coded, since page order
    # in standard.yml can change.
    url = "/t/north-dakota/adult-name-change/standard/"
    assert "Petition for Fee Waiver" not in client.get(url).content.decode()
    response = client.post(url, {"name_change_fee_waiver_needed": "true"})
    assert response.status_code == 302
    assert response["Location"].startswith(f"{url}#interview-")
    stored = dict(
        VariableAnswer.objects.filter(reviewed=True).values_list(
            "variable__name", "value"
        )
    )
    assert stored == {"name_change_fee_waiver_needed": True}
    assert "Petition for Fee Waiver" in client.get(url).content.decode()


# --- the ND output files ----------------------------------------------------

ND_FLOW = "north-dakota-adult-name-change-standard"
ND_URL = "/t/north-dakota/adult-name-change/standard/"


def _download(client, block):
    response = client.get(f"{ND_URL}download/{block}/")
    assert response.status_code == 200, block
    assert f'filename="{block}.' in response["Content-Disposition"]
    # Unfold the lines first, as a UID's length moves the fold.
    return response.content.decode().replace("\r\n ", "")


@pytest.mark.postgres
def test_nd_calendar_and_contacts_download_from_the_real_rows(
    client, db, settings
):
    # A single-court sync, as on the ND instance: a multi-court sync pools
    # every court's contacts into the one table the page lists.
    settings.CORPUS_COURT = "north-dakota"
    corpus_sync(strict=True)
    client.get(ND_URL)
    identity, _ = UserIdentity.objects.get_or_create(
        user=None, session_key=client.session.session_key
    )
    variable_answer_set(
        identity=identity,
        variable=Variable.objects.get(name="name_change_publication_date"),
        value="2026-02-01",
        reviewed=True,
    )

    calendar = _download(client, "calendar")
    assert calendar.count("BEGIN:VEVENT") == 1
    assert (
        f"UID:{ND_FLOW}-calendar-publication_wait@litigantportal.com"
        in calendar
    )
    contacts = _download(client, "contacts")
    assert contacts.count("BEGIN:VCARD") == 5
