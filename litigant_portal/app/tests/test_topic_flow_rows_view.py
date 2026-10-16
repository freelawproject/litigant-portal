"""Topic Flow entry-view tests for the ``TOPIC_FLOW_SOURCE=corpus`` path
: the guided page built from TopicFlow rows.

Every test here needs a database: a small corpus is built in Python and
synced through ``corpus_sync`` (patched over ``corpus_load``, as
``test_corpus_sync.py`` does), then the test client drives the page. The
pure row-to-section functions are covered DB-free in
``test_topic_flow_rows.py``.
"""

import re
from unittest import mock

import pytest

from litigant_portal.app.models import UserIdentity
from litigant_portal.app.selectors.corpus import CorpusSchema
from litigant_portal.app.services import corpus as services
from litigant_portal.app.services.corpus import corpus_sync
from litigant_portal.app.topic_flow.schema import Corpus, InfoSection, Metadata
from litigant_portal.app.views import pages

COURT, TOPIC, ROLE = "alpha", "pets", "standard"
URL = f"/t/{COURT}/{TOPIC}/{ROLE}/"

LAYOUT = [
    "fees",
    "interview",
    "overview",
    "packet",
    "calendar",
    "contacts",
    "resources",
]


def _corpus():
    """One court, one topic, an enabled flow with an authored layout and a
    disabled sibling."""
    variables = {
        "full_name": {
            "name": "full_name",
            "label": "Full name",
            "help_text": "As it appears on your ID.",
            "required": True,
        },
        "pet_kind": {
            "name": "pet_kind",
            "label": "Kind of pet",
            "data_type": "choice",
            "choices": [
                {"value": "dog", "label": "Dog"},
                {"value": "cat", "label": "Cat"},
            ],
        },
        "licensed": {
            "name": "licensed",
            "label": "Already licensed",
            "data_type": "boolean",
        },
        "vaccinated": {
            "name": "vaccinated",
            "label": "Vaccinated",
            "data_type": "boolean",
            "asked_when": {"variable": "licensed", "value": True},
        },
    }
    sections = [
        {
            "id": "overview",
            "heading": "Overview",
            "content": "Read this first.",
        },
        {"id": "fees", "heading": "Fees", "content": "Pay the fee."},
    ]
    interview = [
        {
            "title": "About your pet",
            "description": "A few facts the license needs.",
            "variables": ["full_name", "pet_kind", "licensed", "vaccinated"],
        }
    ]
    return CorpusSchema.model_validate(
        {
            "variables": variables,
            "forms": {},
            "form_acro_fields": {},
            "courts": {
                COURT: {"name": "Alpha", "court_name": "Alpha District Court"}
            },
            "topics": {(COURT, TOPIC): {"title": "Pets"}},
            "flows": {
                (COURT, TOPIC, ROLE): {
                    "name": "Standard",
                    "enabled": True,
                    "sections": sections,
                    "layout": LAYOUT,
                    "interview": interview,
                },
                (COURT, TOPIC, "retired"): {
                    "name": "Retired",
                    "enabled": False,
                    "sections": sections,
                },
            },
        }
    )


@pytest.fixture
def synced(db, settings):
    """The corpus above in the database, with the page reading rows."""
    settings.TOPIC_FLOW_SOURCE = "corpus"
    settings.CORPUS_COURT = None
    with mock.patch.object(services, "corpus_load", return_value=_corpus()):
        corpus_sync()


def _section_ids(html):
    """The page's section anchors, in document order."""
    return re.findall(r'<section id="([^"]+)"', html)


# --- GET render -------------------------------------------------------------


@pytest.mark.postgres
def test_corpus_source_renders_the_synced_flow(client, synced):
    response = client.get(URL)
    assert response.status_code == 200
    assert "pages/topic_flow.html" in [t.name for t in response.templates]
    assert response.context["page_title"] == "Standard"
    assert re.search(
        r"<h1[^>]*>\s*Standard\s*</h1>", response.content.decode()
    )


@pytest.mark.postgres
def test_corpus_source_emits_an_anchor_per_section_key_in_layout_order(
    client, synced
):
    assert _section_ids(client.get(URL).content.decode()) == LAYOUT


@pytest.mark.postgres
def test_corpus_source_renders_each_section_body(client, synced):
    html = client.get(URL).content.decode()
    assert "Read this first." in html
    assert "Pay the fee." in html


@pytest.mark.postgres
def test_corpus_source_lists_every_section_in_the_toc(client, synced):
    html = client.get(URL).content.decode()
    for anchor in LAYOUT:
        assert f'href="#{anchor}"' in html


# --- 404s and the court check -----------------------------------------------


@pytest.mark.postgres
def test_corpus_source_404s_an_unknown_flow(client, synced):
    assert client.get(f"/t/{COURT}/{TOPIC}/nope/").status_code == 404


@pytest.mark.postgres
def test_corpus_source_404s_a_disabled_flow(client, synced):
    assert client.get(f"/t/{COURT}/{TOPIC}/retired/").status_code == 404


@pytest.mark.postgres
def test_corpus_source_404s_the_wrong_court_when_corpus_court_is_set(
    client, synced, settings
):
    settings.CORPUS_COURT = COURT
    assert client.get(URL).status_code == 200
    assert client.get(f"/t/beta/{TOPIC}/{ROLE}/").status_code == 404


@pytest.mark.postgres
def test_corpus_source_accepts_any_court_when_corpus_court_is_unset(
    client, synced
):
    assert client.get(f"/t/beta/{TOPIC}/{ROLE}/").status_code == 200


# --- the default setting ----------------------------------------------------


@pytest.mark.postgres
def test_content_source_still_uses_the_registry(
    client, synced, settings, monkeypatch
):
    # The rows are in the database, but under the default setting the page
    # is whatever the registry says, found or not.
    settings.TOPIC_FLOW_SOURCE = "content"
    registry_corpus = Corpus(
        metadata=Metadata(
            court=COURT, topic=TOPIC, role=ROLE, title="From YAML"
        ),
        sections=[
            InfoSection(
                kind="info", id="intro", heading="Intro", body="Hello."
            )
        ],
    )
    monkeypatch.setattr(pages.registry, "get", lambda *a: registry_corpus)
    response = client.get(URL)
    assert response.context["page_title"] == "From YAML"
    assert _section_ids(response.content.decode()) == ["intro"]

    monkeypatch.setattr(pages.registry, "get", lambda *a: None)
    assert client.get(URL).status_code == 404


# --- identity ---------------------------------------------------------------


@pytest.mark.postgres
def test_corpus_source_first_time_visitor_creates_no_identity(client, synced):
    assert client.get(URL).status_code == 200
    assert UserIdentity.objects.count() == 0
