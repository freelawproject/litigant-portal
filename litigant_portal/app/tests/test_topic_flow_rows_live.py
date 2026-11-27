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
from litigant_portal.app.services.corpus import corpus_sync
from litigant_portal.app.services.topic_flow import variable_answer_set
from litigant_portal.state.selectors import topic_flow_list


@pytest.mark.postgres
def test_every_live_flow_can_revisit_each_applicable_component(
    client, db, settings
):
    settings.CORPUS_COURT = None
    corpus_sync(strict=True)
    flows = topic_flow_list()
    assert flows

    for flow in flows:
        topic = flow.topic.slug
        url = f"/t/{flow.topic.court}/{topic}/{flow.slug}/"
        response = client.get(url)
        assert response.status_code == 200, url
        anchors = [
            link["anchor"] for link in response.context["section_links"]
        ]
        assert len(response.context["rendered_sections"]) == 1
        assert set(flow.sections.values_list("key", flat=True)) <= set(
            anchors
        ), url
        for anchor in anchors:
            selected = client.get(url, {"component": anchor})
            assert selected.status_code == 200, (url, anchor)
            assert re.findall(
                r'<section id="([^"]+)"', selected.content.decode()
            ) == [anchor]

    # Save the "The filing fee" page of the ND standard flow: one boolean
    # the packet reacts to. The anchor is not hard-coded, since page order
    # in standard.yml can change.
    url = "/t/north-dakota/adult-name-change/standard/"
    assert (
        "Petition for Fee Waiver"
        not in client.get(url, {"component": "packet"}).content.decode()
    )
    fee_page = next(
        link["anchor"]
        for link in client.get(url).context["section_links"]
        if link["heading"] == "The filing fee"
    )
    selected = client.get(url, {"component": fee_page})
    response = client.post(
        url,
        {
            "action": "save",
            "component": fee_page,
            "signature": selected.context["rendered_sections"][0].context[
                "signature"
            ],
            "name_change_fee_waiver_needed": "true",
        },
    )
    assert response.status_code == 302
    assert response["Location"] == url
    stored = dict(
        VariableAnswer.objects.filter(reviewed=True).values_list(
            "variable__name", "value"
        )
    )
    assert stored == {"name_change_fee_waiver_needed": True}
    assert (
        "Petition for Fee Waiver"
        in client.get(url, {"component": "packet"}).content.decode()
    )


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
def test_nd_calendar_and_contacts_download_from_the_real_rows(client, db):
    # A single-court sync, as on the ND instance: a multi-court sync pools
    # every court's contacts into the one table the page lists.
    corpus_sync(court="north-dakota", strict=True)
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
