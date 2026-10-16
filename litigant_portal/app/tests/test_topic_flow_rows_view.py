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

from litigant_portal.app.models import UserIdentity, Variable
from litigant_portal.app.selectors.corpus import CorpusSchema
from litigant_portal.app.services import corpus as services
from litigant_portal.app.services.corpus import corpus_sync
from litigant_portal.app.services.topic_flow import variable_answer_set
from litigant_portal.app.topic_flow.schema import (
    Corpus,
    FactGatherSection,
    InfoSection,
    Metadata,
    Question,
)
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
# The anchors the layout renders as: the interview block is one section
# per interview page, numbered in page order.
ANCHORS = [
    "fees",
    "interview-1",
    "interview-2",
    "overview",
    "packet",
    "calendar",
    "contacts",
    "resources",
]


def _corpus():
    """One court, one topic, an enabled flow with an authored layout and a
    disabled sibling. ``first_name`` is in NEVER_PREFILL."""
    variables = {
        "first_name": {"name": "first_name", "label": "First name"},
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
            "title": "About you",
            "variables": ["first_name", "full_name"],
        },
        {
            "title": "About your pet",
            "description": "A few facts the license needs.",
            "variables": ["pet_kind", "licensed", "vaccinated"],
        },
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


def _flat(response):
    """The page with whitespace collapsed, so a multi-line tag matches as
    one string."""
    return re.sub(r"\s+", " ", response.content.decode())


def _field_tag(flat, name):
    """The <input>/<select> element whose name == ``name``."""
    match = re.search(
        rf'<(?:input|select)\b[^>]*name="{re.escape(name)}"[^>]*>', flat
    )
    return match.group(0) if match else ""


def _has_option(flat, value, label):
    """Whether an <option> with this value shows this label."""
    return bool(
        re.search(
            rf'<option value="{re.escape(value)}"[^>]*>{re.escape(label)}</option>',
            flat,
        )
    )


def _store(client, name, value, reviewed=False):
    """Store an answer the way another surface would (the assistant, say),
    on the identity the middleware will resolve for this client."""
    identity, _ = UserIdentity.objects.get_or_create(
        user=None, session_key=client.session.session_key
    )
    variable_answer_set(
        identity=identity,
        variable=Variable.objects.get(name=name),
        value=value,
        reviewed=reviewed,
    )


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
    assert _section_ids(client.get(URL).content.decode()) == ANCHORS


@pytest.mark.postgres
def test_corpus_source_renders_each_section_body(client, synced):
    html = client.get(URL).content.decode()
    assert "Read this first." in html
    assert "Pay the fee." in html


@pytest.mark.postgres
def test_corpus_source_lists_every_section_in_the_left_region(client, synced):
    html = client.get(URL).content.decode()
    for anchor in ANCHORS:
        assert f'href="#{anchor}"' in html


# --- interview pages as forms -----------------------------------------------


@pytest.mark.postgres
def test_each_interview_page_renders_a_post_form_with_a_field_per_variable(
    client, synced
):
    flat = _flat(client.get(URL))
    assert flat.count('method="post"') == 2
    assert "csrfmiddlewaretoken" in flat
    for name in ("first_name", "full_name", "pet_kind", "licensed"):
        assert _field_tag(flat, name), name
    assert re.search(r"<h2[^>]*>\s*About your pet\s*</h2>", flat)


@pytest.mark.postgres
def test_choice_field_renders_option_values_and_labels(client, synced):
    flat = _flat(client.get(URL))
    assert _has_option(flat, "dog", "Dog")
    assert _has_option(flat, "cat", "Cat")


@pytest.mark.postgres
def test_boolean_field_renders_a_yes_no_select(client, synced):
    flat = _flat(client.get(URL))
    assert _field_tag(flat, "licensed").startswith("<select")
    assert _has_option(flat, "true", "Yes")
    assert _has_option(flat, "false", "No")


@pytest.mark.postgres
def test_required_variable_marks_the_field_required_and_optional_stays_unmarked(
    client, synced
):
    flat = _flat(client.get(URL))
    assert re.search(r"\brequired\b", _field_tag(flat, "full_name"))
    assert not re.search(r"\brequired\b", _field_tag(flat, "pet_kind"))


@pytest.mark.postgres
def test_help_text_renders_beside_the_field(client, synced):
    flat = _flat(client.get(URL))
    assert 'aria-describedby="full_name-help"' in _field_tag(flat, "full_name")
    assert re.search(
        r'<p id="full_name-help"[^>]*>As it appears on your ID\.</p>', flat
    )


@pytest.mark.postgres
def test_page_description_renders_above_the_fields(client, synced):
    flat = _flat(client.get(URL))
    description = flat.index("A few facts the license needs.")
    assert description < flat.index('name="pet_kind"')
    # The page without a description renders no empty paragraph.
    assert flat.count('<p class="mb-4 text-greyscale-700">') == 1


@pytest.mark.postgres
def test_stored_answer_prefills_the_field(client, synced):
    _store(client, "pet_kind", "dog")
    _store(client, "licensed", False)
    flat = _flat(client.get(URL))
    assert re.search(r'<option value="dog"[^>]*selected', flat)
    assert re.search(r'<option value="false"[^>]*selected', flat)


@pytest.mark.postgres
def test_gated_field_appears_after_the_gate_answer_is_stored(client, synced):
    assert not _field_tag(_flat(client.get(URL)), "vaccinated")
    _store(client, "licensed", False)
    assert not _field_tag(_flat(client.get(URL)), "vaccinated")
    _store(client, "licensed", True)
    assert _field_tag(_flat(client.get(URL)), "vaccinated")


@pytest.mark.postgres
def test_protected_field_never_echoes_the_stored_value(client, synced):
    before = _flat(client.get(URL))
    assert 'name="first_name__clear"' not in before
    _store(client, "first_name", "Sandra")
    after = _flat(client.get(URL))
    assert "Sandra" not in after
    assert re.search(
        r'<input[^>]*type="checkbox"[^>]*name="first_name__clear"', after
    )


@pytest.mark.postgres
def test_content_path_choice_options_are_unchanged(
    client, synced, settings, monkeypatch
):
    # The content renderer now hands the template {value, label} dicts; its
    # options must read exactly as before the shape change.
    settings.TOPIC_FLOW_SOURCE = "content"
    registry_corpus = Corpus(
        metadata=Metadata(court=COURT, topic=TOPIC, role=ROLE, title="T"),
        sections=[
            FactGatherSection(
                kind="fact_gather",
                id="key_dates",
                heading="Your dates",
                questions=[
                    Question(
                        id="filing_county",
                        label="County",
                        type="choice",
                        choices=["Cass", "Burleigh"],
                    )
                ],
            )
        ],
    )
    monkeypatch.setattr(pages.registry, "get", lambda *a: registry_corpus)
    flat = _flat(client.get(URL))
    assert _has_option(flat, "Cass", "Cass")
    assert _has_option(flat, "Burleigh", "Burleigh")


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
