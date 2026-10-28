"""Topic Flow entry-view tests: the guided page built from TopicFlow rows,
its downloads and the docassemble handoff.

The URL-resolution tests are DB-free. Every other test needs a database: a
small corpus is built in Python and synced through ``corpus_sync`` (patched
over ``corpus_load``, as ``test_corpus_sync.py`` does), then the test client
drives the page. The pure row-to-section functions are covered DB-free in
``test_topic_flow_rows.py``.
"""

import re
from datetime import date
from unittest import mock

import pytest
import vobject
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from litigant_portal.app.models import (
    TopicFlow,
    UserIdentity,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.selectors.corpus import CorpusSchema
from litigant_portal.app.services import corpus as services
from litigant_portal.app.services.corpus import corpus_sync
from litigant_portal.app.services.docassemble import DocassembleError
from litigant_portal.app.services.topic_flow import variable_answer_set
from litigant_portal.app.views import topic_flow as topic_flow_views

COURT, TOPIC, ROLE = "alpha", "pets", "standard"
URL = f"/t/{COURT}/{TOPIC}/{ROLE}/"
DOWNLOAD_URL = f"{URL}download/"
INTERVIEW_URL = f"{URL}interview/"

# The docassemble handoff, shaped like the ND flow's: one private
# variable and one plain one, renamed for the interview.
REFERENCE = "docassemble.test:data/questions/petition.yml"
PREFILL = {"full_name": "petitioner_name", "license_date": "licensed_on"}
DA_BASE = "https://da.example.gov/interview"
DA_LAUNCH = (
    f"{DA_BASE}/interview?i=docassemble.test%3Adata%2Fquestions%2Fpetition.yml"
)
DA_RESUME = "https://da.example.gov/interview/launch?c=token"

CONTACTS = [
    {
        "id": "clerk",
        "name": "Clerk of Court",
        "phone": "555-1234",
        "address": "100 Main St",
        "hours": "9-4 M-F",
    },
    {"id": "aid", "name": "Legal Aid", "email": "help@aid.example"},
]
# A second court's rows, synced alongside (CORPUS_COURT unset); the alpha
# page and its download must leave them out.
BETA_CONTACTS = [
    {"id": "beta-clerk", "name": "Beta Clerk", "phone": "555-9999"}
]
BETA_RESOURCES = [
    {"id": "beta-help", "label": "Beta Help", "url": "https://beta.example"}
]
RESOURCES = [
    {"id": "self-help", "label": "Self Help", "url": "https://help.example"},
    {
        "id": "rules",
        "label": "Rules",
        "url": "https://rules.example",
        "note": "Chapter 3.",
    },
]

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
    """One court with two contacts and two resources, one topic, an enabled
    flow with an authored layout and a disabled sibling, plus a second court
    with a contact and a resource of its own. ``first_name`` is private."""
    variables = {
        # Required and private, as in the real glossary.
        "first_name": {
            "name": "first_name",
            "label": "First name",
            "required": True,
            "private": True,
        },
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
            "default": "cat",
        },
        "licensed": {
            "name": "licensed",
            "label": "Already licensed",
            "question": "Is your pet already licensed?",
            "data_type": "boolean",
        },
        "vaccinated": {
            "name": "vaccinated",
            "label": "Vaccinated",
            "data_type": "boolean",
            "asked_when": {"variable": "licensed", "value": True},
        },
        "pet_count": {
            "name": "pet_count",
            "label": "How many pets",
            "data_type": "number",
        },
        "license_date": {
            "name": "license_date",
            "label": "Date licensed",
            "data_type": "date",
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
            "variables": [
                "pet_kind",
                "licensed",
                "vaccinated",
                "pet_count",
                "license_date",
            ],
        },
    ]
    # A form with the court's PDF url and one without; the checklist joins
    # the packet only once the pet is licensed.
    forms = {
        "petition": {
            "name": "License petition",
            "url": "https://alpha.example/petition.pdf",
            "fields": [{"pdf_field": "Name", "template": "{full_name}"}],
        },
        "checklist": {"name": "Licensed pet checklist", "fields": []},
    }
    packet = [
        {"form": "petition"},
        {
            "form": "checklist",
            "when": {"variable": "licensed", "value": True},
        },
    ]
    return CorpusSchema.model_validate(
        {
            "variables": variables,
            "forms": forms,
            "form_acro_fields": {"petition": {"Name": "/Tx"}, "checklist": {}},
            "courts": {
                COURT: {
                    "name": "Alpha",
                    "court_name": "Alpha District Court",
                    "contacts": CONTACTS,
                    "resources": RESOURCES,
                },
                "beta": {
                    "name": "Beta",
                    "court_name": "Beta Municipal Court",
                    "contacts": BETA_CONTACTS,
                    "resources": BETA_RESOURCES,
                },
            },
            "topics": {(COURT, TOPIC): {"title": "Pets"}},
            "flows": {
                (COURT, TOPIC, ROLE): {
                    "name": "Standard",
                    "enabled": True,
                    "sections": sections,
                    "layout": LAYOUT,
                    "interview": interview,
                    "packet": packet,
                    "handoff": {
                        "interview_reference": REFERENCE,
                        "interview_prefill": PREFILL,
                    },
                    "deadlines": [
                        {
                            "id": "renewal",
                            "label": "License renewal due",
                            "description": "One year after licensing.",
                            "offset_days": 365,
                            "offset_from": "license_date",
                        }
                    ],
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
def synced(db, settings, tmp_path):
    """The corpus above in the database. The forms directory holds stand-in
    PDF bytes for the sync's file writes."""
    settings.CORPUS_COURT = None
    corpus = _corpus()
    for slug in corpus.forms:
        (tmp_path / f"{slug}.pdf").write_bytes(b"%PDF-stand-in")
    with (
        mock.patch.object(services, "corpus_load", return_value=corpus),
        mock.patch.object(services, "FORMS_DIR", tmp_path),
    ):
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


def _store(client, name, value, reviewed=False, evidence=None):
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
        evidence=evidence,
    )


# --- URL resolution (DB-free) -----------------------------------------------


def test_three_segment_url_resolves_to_topic_flow_view():
    assert resolve(URL).view_name == "pages:topic_flow"


def test_two_segment_url_no_longer_resolves():
    # The 2-seg deep link went with the prompts package (#1049). `slug` never
    # crosses a `/`, so the 3-seg flow URL must not absorb it either.
    with pytest.raises(Resolver404):
        resolve(f"/t/{COURT}/{TOPIC}/")


def test_topic_flow_url_reverses_with_three_segments():
    kwargs = {"court": COURT, "topic": TOPIC, "role": ROLE}
    assert reverse("pages:topic_flow", kwargs=kwargs) == URL


def test_download_url_resolves_and_reverses_with_the_output_id():
    assert (
        resolve(f"{DOWNLOAD_URL}calendar/").view_name
        == "pages:topic_flow_download"
    )
    kwargs = {"court": COURT, "topic": TOPIC, "role": ROLE}
    assert (
        reverse(
            "pages:topic_flow_download",
            kwargs={**kwargs, "output_id": "calendar"},
        )
        == f"{DOWNLOAD_URL}calendar/"
    )


def test_interview_url_resolves_and_reverses():
    assert resolve(INTERVIEW_URL).view_name == "pages:topic_flow_interview"
    kwargs = {"court": COURT, "topic": TOPIC, "role": ROLE}
    assert (
        reverse("pages:topic_flow_interview", kwargs=kwargs) == INTERVIEW_URL
    )


# --- GET render -------------------------------------------------------------


@pytest.mark.postgres
def test_get_renders_the_synced_flow(client, synced):
    response = client.get(URL)
    assert response.status_code == 200
    assert "pages/topic_flow.html" in [t.name for t in response.templates]
    assert response.context["page_title"] == "Standard"
    assert re.search(
        r"<h1[^>]*>\s*Standard\s*</h1>", response.content.decode()
    )


@pytest.mark.postgres
def test_page_emits_an_anchor_per_section_key_in_layout_order(client, synced):
    assert _section_ids(client.get(URL).content.decode()) == ANCHORS


@pytest.mark.postgres
def test_page_renders_each_section_body(client, synced):
    html = client.get(URL).content.decode()
    assert "Read this first." in html
    assert "Pay the fee." in html


@pytest.mark.postgres
def test_page_lists_every_section_in_the_left_region(client, synced):
    html = client.get(URL).content.decode()
    for anchor in ANCHORS:
        assert f'href="#{anchor}"' in html


# --- interview pages as forms -----------------------------------------------


@pytest.mark.postgres
def test_each_interview_page_renders_a_post_form_with_a_field_per_variable(
    client, synced
):
    flat = _flat(client.get(URL))
    # Interview forms only: the frame's "Start over" dialog is a POST too.
    assert len(re.findall(r'<form[^>]*aria-labelledby="interview-', flat)) == 2
    assert "csrfmiddlewaretoken" in flat
    for name in ("first_name", "full_name", "pet_kind", "licensed"):
        assert _field_tag(flat, name), name
    assert re.search(r"<h2[^>]*>\s*About your pet\s*</h2>", flat)


@pytest.mark.postgres
def test_each_interview_form_is_named_by_its_section_heading(client, synced):
    flat = _flat(client.get(URL))
    assert re.search(
        r'<h2 id="interview-2-heading"[^>]*>\s*About your pet\s*</h2>', flat
    )
    assert re.search(
        r'<form[^>]*aria-labelledby="interview-2-heading"[^>]*>', flat
    )


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
def test_an_authored_question_is_the_fields_label(client, synced):
    flat = _flat(client.get(URL))
    assert re.search(
        r'<label for="licensed"[^>]*>\s*Is your pet already licensed\?', flat
    )
    assert "Already licensed" not in flat


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
    assert flat.count("A few facts the license needs.") == 1


@pytest.mark.postgres
def test_glossary_default_preselects_until_an_answer_is_stored(client, synced):
    flat = _flat(client.get(URL))
    assert re.search(r'<option value="cat"[^>]*selected', flat)
    _store(client, "pet_kind", "dog")
    flat = _flat(client.get(URL))
    assert re.search(r'<option value="dog"[^>]*selected', flat)
    assert not re.search(r'<option value="cat"[^>]*selected', flat)


@pytest.mark.postgres
def test_stored_answers_prefill_and_only_unreviewed_evidence_is_shown(
    client, synced
):
    _store(
        client,
        "pet_kind",
        "dog",
        evidence={"quote": "I own a <dog>."},
    )
    _store(
        client,
        "licensed",
        False,
        evidence={"quote": "License: none", "upload_id": "document-id"},
    )
    _store(
        client,
        "full_name",
        "Jane Doe",
        reviewed=True,
        evidence={"quote": "My full name is Jane Doe."},
    )
    flat = _flat(client.get(URL))
    assert re.search(r'<option value="dog"[^>]*selected', flat)
    assert re.search(r'<option value="false"[^>]*selected', flat)
    assert "Because you said: I own a &lt;dog&gt;." in flat
    assert "From your document: License: none" in flat
    assert "My full name is Jane Doe." not in flat
    assert "I own a <dog>." not in flat


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
    _store(
        client,
        "first_name",
        "Sandra",
        evidence={"quote": "My name is Sandra."},
    )
    after = _flat(client.get(URL))
    # The input stays blank (the briefcase panel may still list the fact).
    field = _field_tag(after, "first_name")
    assert field and "Sandra" not in field
    assert "My name is Sandra." not in after
    assert re.search(
        r'<input[^>]*type="checkbox"[^>]*name="first_name__clear"', after
    )
    # The unprotected sibling shows its value, so it never needs the box.
    assert 'name="full_name__clear"' not in after


@pytest.mark.postgres
def test_date_field_disables_browser_autocomplete(client, synced):
    # #638: on a shared terminal the browser's own autofill could otherwise
    # suggest a prior user's typed date, independent of our session.
    flat = _flat(client.get(URL))
    assert 'autocomplete="off"' in _field_tag(flat, "license_date")


# --- packet -----------------------------------------------------------------


def _packet(client):
    """The packet block's HTML, whitespace collapsed."""
    flat = _flat(client.get(URL))
    block = flat[flat.index('<section id="packet"') :]
    return block[: block.index("<section id=", 1)]


@pytest.mark.postgres
def test_packet_lists_each_form_in_order(client, synced):
    _store(client, "licensed", True)
    block = _packet(client)
    assert block.index("License petition") < block.index(
        "Licensed pet checklist"
    )


@pytest.mark.postgres
def test_packet_form_with_a_url_is_a_link_and_without_is_plain_text(
    client, synced
):
    _store(client, "licensed", True)
    block = _packet(client)
    assert re.search(
        r'<a [^>]*href="https://alpha.example/petition.pdf"[^>]*target="_blank"'
        r"[^>]*>\s*License petition",
        block,
    )
    assert re.search(r"<li>\s*Licensed pet checklist\s*</li>", block)


@pytest.mark.postgres
def test_conditional_form_is_hidden_until_its_answer_is_stored(client, synced):
    assert "Licensed pet checklist" not in _packet(client)
    _store(client, "licensed", False)
    assert "Licensed pet checklist" not in _packet(client)


@pytest.mark.postgres
def test_conditional_form_appears_once_the_answer_matches(client, synced):
    _store(client, "licensed", True)
    assert "Licensed pet checklist" in _packet(client)


@pytest.mark.postgres
def test_packet_has_no_interview_button_without_a_handoff(client, synced):
    block = _packet(client)
    assert "License petition" in block
    assert "Fill out your forms" not in block
    assert f"{URL}interview/" not in block


# --- the docassemble handoff ------------------------------------------------


class _DocassembleClient:
    """Stands in for docassemble_session_create, recording its payload."""

    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def __call__(self, *, interview, variables):
        self.calls.append({"interview": interview, "variables": variables})
        if self.error:
            raise self.error
        return DA_RESUME


@pytest.fixture
def docassemble(settings, monkeypatch):
    settings.DOCASSEMBLE_BASE_URL = DA_BASE
    settings.DOCASSEMBLE_PUBLIC_URL = None
    client = _DocassembleClient()
    monkeypatch.setattr(topic_flow_views, "docassemble_session_create", client)
    return client


@pytest.mark.postgres
def test_packet_posts_the_handoff_when_the_flow_has_a_reference(
    client, synced, docassemble
):
    block = _packet(client)
    assert re.search(
        rf'<form[^>]*method="post"[^>]*action="{re.escape(INTERVIEW_URL)}"',
        block,
    )
    assert "Fill out your forms" in block


@pytest.mark.postgres
def test_packet_hides_the_handoff_without_docassemble_configured(
    client, synced, settings
):
    settings.DOCASSEMBLE_BASE_URL = None
    settings.DOCASSEMBLE_PUBLIC_URL = None
    block = _packet(client)
    assert "License petition" in block
    assert "Fill out your forms" not in block
    assert INTERVIEW_URL not in block


@pytest.mark.postgres
def test_interview_post_sends_reviewed_answers_under_their_interview_names(
    client, synced, docassemble
):
    _store(client, "full_name", "Jane Doe", reviewed=True)
    _store(client, "license_date", "2026-02-01", reviewed=True)
    _store(client, "pet_kind", "dog", reviewed=True)
    response = client.post(INTERVIEW_URL)
    assert response.status_code == 302
    assert response["Location"] == DA_RESUME
    assert docassemble.calls == [
        {
            "interview": REFERENCE,
            # pet_kind is reviewed but unmapped, so it stays home.
            "variables": {
                "petitioner_name": "Jane Doe",
                "licensed_on": "2026-02-01",
            },
        }
    ]


@pytest.mark.postgres
def test_interview_post_never_sends_an_unreviewed_answer(
    client, synced, docassemble
):
    _store(client, "full_name", "Jane Doe", reviewed=True)
    _store(client, "license_date", "2026-02-01", reviewed=False)
    client.post(INTERVIEW_URL)
    assert docassemble.calls[0]["variables"] == {"petitioner_name": "Jane Doe"}


@pytest.mark.postgres
def test_interview_post_with_nothing_to_prefill_goes_to_the_plain_link(
    client, synced, docassemble
):
    _store(client, "pet_kind", "dog", reviewed=True)
    assert client.post(INTERVIEW_URL)["Location"] == DA_LAUNCH
    assert docassemble.calls == []


@pytest.mark.postgres
def test_a_fresh_guest_goes_straight_to_the_plain_interview(
    client, synced, docassemble
):
    # No identity row minted for a visitor who answered nothing.
    assert client.post(INTERVIEW_URL)["Location"] == DA_LAUNCH
    assert docassemble.calls == []
    assert UserIdentity.objects.count() == 0


@pytest.mark.postgres
def test_a_flow_with_an_empty_prefill_map_links_out_without_a_session(
    client, synced, docassemble
):
    TopicFlow.objects.filter(slug=ROLE).update(interview_prefill={})
    _store(client, "full_name", "Jane Doe", reviewed=True)
    assert client.post(INTERVIEW_URL)["Location"] == DA_LAUNCH
    assert docassemble.calls == []


@pytest.mark.postgres
def test_a_changed_answer_is_sent_at_its_new_value(
    client, synced, docassemble
):
    _store(client, "full_name", "Jane Doe", reviewed=True)
    _store(client, "full_name", "Jane Roe", reviewed=True)
    client.post(INTERVIEW_URL)
    assert docassemble.calls[0]["variables"] == {"petitioner_name": "Jane Roe"}


@pytest.mark.postgres
def test_the_same_answer_is_sent_once_the_litigant_confirms_it(
    client, synced, docassemble
):
    _store(client, "full_name", "Jane Doe", reviewed=False)
    client.post(URL, {"first_name": "", "full_name": "Jane Doe"})
    client.post(INTERVIEW_URL)
    assert docassemble.calls[0]["variables"] == {"petitioner_name": "Jane Doe"}


@pytest.mark.postgres
def test_an_answer_confirmed_through_the_chat_endpoint_reaches_the_payload(
    client, synced, docassemble
):
    _store(client, "full_name", "Jane Doe", reviewed=False)
    client.post(
        "/facts/confirm/",
        {"names": ["full_name"], "as_of": timezone.now().isoformat()},
    )
    client.post(INTERVIEW_URL)
    assert docassemble.calls[0]["variables"] == {"petitioner_name": "Jane Doe"}


@pytest.mark.postgres
def test_an_assistant_overwrite_drops_a_confirmed_answer_again(
    client, synced, docassemble
):
    _store(client, "full_name", "Jane Doe", reviewed=True)
    _store(client, "full_name", "Jane Roe", reviewed=False)
    assert client.post(INTERVIEW_URL)["Location"] == DA_LAUNCH
    assert docassemble.calls == []


@pytest.mark.postgres
def test_answers_still_reach_the_payload_after_login(
    client, synced, docassemble
):
    client.post(URL, {"first_name": "", "full_name": "Jane Doe"})
    # The GET is load-bearing: AnonymousSessionKeyMiddleware only records
    # the key on a request that already carries a session cookie, and the
    # POST above created the session mid-request. client.login() skips
    # middleware, so without it the merge has no key to work from.
    client.get(URL)
    user = get_user_model().objects.create_user(username="u", password="p")
    assert client.login(username="u", password="p")
    client.post(INTERVIEW_URL)
    assert docassemble.calls[0]["variables"] == {"petitioner_name": "Jane Doe"}
    assert UserIdentity.objects.filter(user=user).exists()


@pytest.mark.postgres
def test_interview_post_falls_back_to_the_plain_link_when_the_session_fails(
    client, synced, settings, monkeypatch
):
    settings.DOCASSEMBLE_BASE_URL = DA_BASE
    settings.DOCASSEMBLE_PUBLIC_URL = None
    monkeypatch.setattr(
        topic_flow_views,
        "docassemble_session_create",
        _DocassembleClient(error=DocassembleError("down")),
    )
    _store(client, "full_name", "Jane Doe", reviewed=True)
    response = client.post(INTERVIEW_URL)
    assert response.status_code == 302
    assert response["Location"] == DA_LAUNCH


@pytest.mark.postgres
def test_an_unexpected_client_error_is_not_swallowed(
    client, synced, settings, monkeypatch
):
    # Only DocassembleError means "fall back"; a bug in our own code must
    # surface rather than hide behind an unprefilled interview.
    settings.DOCASSEMBLE_BASE_URL = DA_BASE
    settings.DOCASSEMBLE_PUBLIC_URL = None
    monkeypatch.setattr(
        topic_flow_views,
        "docassemble_session_create",
        _DocassembleClient(error=TypeError("bug")),
    )
    _store(client, "full_name", "Jane Doe", reviewed=True)
    with pytest.raises(TypeError):
        client.post(INTERVIEW_URL)


@pytest.mark.postgres
def test_interview_get_is_rejected(client, synced, docassemble):
    assert client.get(INTERVIEW_URL).status_code == 405
    assert docassemble.calls == []


@pytest.mark.postgres
def test_interview_post_on_a_flow_without_a_reference_is_404(
    client, synced, docassemble
):
    TopicFlow.objects.filter(slug=ROLE).update(interview_reference="")
    assert client.post(INTERVIEW_URL).status_code == 404
    assert (
        client.post(f"/t/{COURT}/{TOPIC}/nope/interview/").status_code == 404
    )
    assert docassemble.calls == []


@pytest.mark.postgres
def test_interview_post_without_docassemble_configured_is_404(
    client, synced, settings
):
    # The packet block hides the button in this state; a POST that arrives
    # anyway must not fall back onto a host named by content.
    settings.DOCASSEMBLE_BASE_URL = None
    settings.DOCASSEMBLE_PUBLIC_URL = None
    assert client.post(INTERVIEW_URL).status_code == 404


@pytest.mark.postgres
def test_interview_target_reads_the_flow_row_without_its_graph(
    synced, django_assert_num_queries
):
    # The handoff needs two columns of the flow row, not the sections,
    # pages and forms the page prefetches.
    with django_assert_num_queries(1):
        target = topic_flow_views._interview_target(COURT, TOPIC, ROLE)
    assert target == (REFERENCE, PREFILL)


@pytest.mark.postgres
def test_csrf_failure_on_the_interview_falls_back_to_the_plain_link(
    synced, docassemble
):
    response = Client(enforce_csrf_checks=True).post(INTERVIEW_URL)
    assert response.status_code == 302
    assert response["Location"] == DA_LAUNCH


@pytest.mark.postgres
def test_csrf_failure_on_an_unknown_flow_keeps_the_default_page(
    synced, docassemble
):
    response = Client(enforce_csrf_checks=True).post(
        f"/t/{COURT}/{TOPIC}/nope/interview/"
    )
    assert response.status_code == 403


@pytest.mark.postgres
def test_csrf_failure_on_a_flow_without_an_interview_keeps_the_default_page(
    synced, docassemble
):
    TopicFlow.objects.filter(slug=ROLE).update(interview_reference="")
    response = Client(enforce_csrf_checks=True).post(INTERVIEW_URL)
    assert response.status_code == 403


@pytest.mark.postgres
def test_csrf_failure_without_docassemble_keeps_the_default_page(
    synced, settings
):
    settings.DOCASSEMBLE_BASE_URL = None
    settings.DOCASSEMBLE_PUBLIC_URL = None
    response = Client(enforce_csrf_checks=True).post(INTERVIEW_URL)
    assert response.status_code == 403


@pytest.mark.postgres
def test_csrf_failure_elsewhere_keeps_the_default_page(synced, docassemble):
    response = Client(enforce_csrf_checks=True).post(
        URL, {"first_name": "", "full_name": "Jane Doe"}
    )
    assert response.status_code == 403


# --- calendar ---------------------------------------------------------------


def _calendar(client):
    """The calendar block's HTML, whitespace collapsed."""
    flat = _flat(client.get(URL))
    block = flat[flat.index('<section id="calendar"') :]
    return block[: block.index("<section id=", 1)]


@pytest.mark.postgres
def test_calendar_shows_the_hint_until_the_source_date_is_stored(
    client, synced
):
    block = _calendar(client)
    assert "License renewal due" in block
    assert "One year after licensing." in block
    assert "Enter your dates above" in block
    assert "<time" not in block
    assert f"{DOWNLOAD_URL}calendar/" not in block


@pytest.mark.postgres
def test_calendar_shows_the_computed_date_and_the_download_link_once_stored(
    client, synced
):
    _store(client, "license_date", "2026-02-01")
    block = _calendar(client)
    assert re.search(
        r'<time datetime="2027-02-01">\s*Monday, February 1, 2027\s*</time>',
        block,
    )
    assert "Enter your dates above" not in block
    assert f'href="{DOWNLOAD_URL}calendar/"' in block
    assert "Add to calendar" in block


@pytest.mark.postgres
def test_calendar_download_streams_the_computed_deadline_as_an_event(
    client, synced
):
    _store(client, "license_date", "2026-02-01")
    response = client.get(f"{DOWNLOAD_URL}calendar/")
    assert response.status_code == 200
    assert "text/calendar" in response["Content-Type"]
    assert (
        'attachment; filename="calendar.ics"'
        in response["Content-Disposition"]
    )
    cal = vobject.readOne(response.content.decode())
    assert cal.vevent.summary.value == "License renewal due"
    assert cal.vevent.description.value == "One year after licensing."
    assert cal.vevent.dtstart.value == date(2027, 2, 1)


@pytest.mark.postgres
def test_calendar_download_without_dates_is_an_empty_but_valid_calendar(
    client, synced
):
    response = client.get(f"{DOWNLOAD_URL}calendar/")
    assert response.status_code == 200
    cal = vobject.readOne(response.content.decode())
    assert "vevent" not in cal.contents


@pytest.mark.postgres
def test_calendar_download_uid_names_the_flow_and_the_deadline_key(
    client, synced
):
    _store(client, "license_date", "2026-02-01")
    cal = vobject.readOne(
        client.get(f"{DOWNLOAD_URL}calendar/").content.decode()
    )
    assert (
        cal.vevent.uid.value
        == f"{COURT}-{TOPIC}-{ROLE}-calendar-renewal@litigantportal.com"
    )


# --- contacts and resources blocks ------------------------------------------


@pytest.mark.postgres
def test_resources_block_renders_each_court_resource_as_a_link(client, synced):
    flat = _flat(client.get(URL))
    block = flat[flat.index('<section id="resources"') :]
    links = re.findall(r'<a [^>]*href="([^"]+)"[^>]*>', block)
    assert links[:2] == ["https://help.example", "https://rules.example"]
    assert re.search(
        r'<a [^>]*href="https://rules.example"[^>]*target="_blank"', block
    )
    assert "Chapter 3." in block


@pytest.mark.postgres
def test_contacts_block_renders_a_card_per_court_contact(client, synced):
    flat = _flat(client.get(URL))
    block = flat[flat.index('<section id="contacts"') :]
    block = block[: block.index('<section id="resources"')]
    assert block.index("Clerk of Court") < block.index("Legal Aid")
    assert 'href="tel:555-1234"' in block
    assert 'href="mailto:help@aid.example"' in block
    assert "100 Main St" in block
    assert "Hours: 9-4 M-F" in block


@pytest.mark.postgres
def test_contacts_and_resources_blocks_leave_out_another_courts_rows(
    client, synced
):
    flat = _flat(client.get(URL))
    assert "Clerk of Court" in flat
    assert "Beta Clerk" not in flat
    assert "https://beta.example" not in flat


@pytest.mark.postgres
def test_contacts_block_links_to_the_contacts_download(client, synced):
    flat = _flat(client.get(URL))
    assert f'href="{DOWNLOAD_URL}contacts/"' in flat
    assert "Add to contacts" in flat


@pytest.mark.postgres
def test_contacts_download_streams_a_vcard_per_court_contact(client, synced):
    response = client.get(f"{DOWNLOAD_URL}contacts/")
    assert response.status_code == 200
    assert "text/vcard" in response["Content-Type"]
    assert (
        'attachment; filename="contacts.vcf"'
        in response["Content-Disposition"]
    )
    cards = list(vobject.readComponents(response.content.decode()))
    # The other court's clerk is synced too but is not in this court's file.
    assert [card.fn.value for card in cards] == ["Clerk of Court", "Legal Aid"]
    assert cards[0].tel.value == "555-1234"
    assert "Hours: 9-4 M-F" in cards[0].note.value
    assert cards[1].email.value == "help@aid.example"


@pytest.mark.postgres
def test_contacts_download_uid_names_the_flow_and_the_contact_key(
    client, synced
):
    cards = list(
        vobject.readComponents(
            client.get(f"{DOWNLOAD_URL}contacts/").content.decode()
        )
    )
    assert [card.uid.value for card in cards] == [
        f"{COURT}-{TOPIC}-{ROLE}-contacts-clerk@litigantportal.com",
        f"{COURT}-{TOPIC}-{ROLE}-contacts-aid@litigantportal.com",
    ]


@pytest.mark.postgres
def test_download_of_an_unknown_output_is_404(client, synced):
    # Only the two output block names download; a section key is not an id.
    for output_id in ("save_contacts", "overview", "nope"):
        assert client.get(f"{DOWNLOAD_URL}{output_id}/").status_code == 404
    assert (
        client.get(f"/t/{COURT}/{TOPIC}/nope/download/contacts/").status_code
        == 404
    )


# --- 404s and the court check -----------------------------------------------


@pytest.mark.postgres
def test_unknown_flow_is_404(client, synced):
    assert client.get(f"/t/{COURT}/{TOPIC}/nope/").status_code == 404


@pytest.mark.postgres
def test_disabled_flow_is_404(client, synced):
    assert client.get(f"/t/{COURT}/{TOPIC}/retired/").status_code == 404


@pytest.mark.postgres
def test_the_wrong_court_is_404_when_corpus_court_is_set(
    client, synced, settings
):
    settings.CORPUS_COURT = COURT
    assert client.get(URL).status_code == 200
    assert client.get(f"/t/beta/{TOPIC}/{ROLE}/").status_code == 404


@pytest.mark.postgres
def test_a_court_that_does_not_own_the_topic_row_is_404(client, synced):
    """``beta`` is a synced court, but ``pets`` is alpha's topic."""
    assert client.get(URL).status_code == 200
    assert client.get(f"/t/beta/{TOPIC}/{ROLE}/").status_code == 404
    assert client.get(f"/t/nowhere/{TOPIC}/{ROLE}/").status_code == 404


# --- identity ---------------------------------------------------------------


@pytest.mark.postgres
def test_first_time_visitor_creates_no_identity(client, synced):
    assert client.get(URL).status_code == 200
    assert UserIdentity.objects.count() == 0


@pytest.mark.postgres
def test_post_owns_answers_by_the_visitor_identity(client, synced):
    client.post(URL, {"pet_kind": "dog"})
    identity = UserIdentity.objects.get()
    assert identity.session_key == client.session.session_key
    assert list(identity.variable_answers.all()) == list(
        VariableAnswer.objects.all()
    )


@pytest.mark.postgres
def test_answers_survive_login(client, synced):
    # What a guest saved is still theirs, and still confirmed, after the
    # identity merge runs on login.
    client.post(URL, {"pet_kind": "dog"})
    client.get(URL)
    user = get_user_model().objects.create_user(username="u", password="p")
    assert client.login(username="u", password="p")
    flat = _flat(client.get(URL))
    assert re.search(r'<option value="dog"[^>]*selected', flat)
    answer = VariableAnswer.objects.get()
    assert answer.identity.user == user
    assert answer.reviewed


# --- POST: saving answers ---------------------------------------------------


def _rows():
    """``{variable_name: (value, reviewed)}`` for the single visitor."""
    return {
        answer.variable.name: (answer.value, answer.reviewed)
        for answer in VariableAnswer.objects.select_related("variable")
    }


def _values():
    return {name: value for name, (value, _reviewed) in _rows().items()}


PET_PAGE = {"pet_kind": "dog", "licensed": "true", "pet_count": "2"}


@pytest.mark.postgres
def test_post_persists_answers_and_redirects_to_the_section_anchor(
    client, synced
):
    # licensed=false reveals nothing, so the anchor is the section's own.
    response = client.post(URL, {**PET_PAGE, "licensed": "false"})
    assert response.status_code == 302
    assert response["Location"] == f"{URL}#interview-2"
    assert _values() == {"pet_kind": "dog", "licensed": False, "pet_count": 2}


@pytest.mark.postgres
def test_a_save_that_reveals_a_question_redirects_to_that_field(
    client, synced
):
    response = client.post(URL, {"licensed": "true"})
    assert response["Location"] == f"{URL}#vaccinated"
    response = client.post(URL, {"licensed": "false"})
    assert response["Location"] == f"{URL}#interview-2"


@pytest.mark.postgres
def test_post_marks_saved_answers_reviewed(client, synced):
    evidence = {"quote": "I own a dog."}
    _store(client, "pet_kind", "dog", evidence=evidence)
    _store(client, "licensed", False, evidence={"quote": "No license yet."})
    before = VariableAnswer.objects.get(variable__name="pet_kind")
    client.post(URL, PET_PAGE)
    assert all(reviewed for _value, reviewed in _rows().values())
    unchanged = VariableAnswer.objects.get(variable__name="pet_kind")
    assert unchanged.evidence == evidence
    assert unchanged.updated_at == before.updated_at
    changed = VariableAnswer.objects.get(variable__name="licensed")
    assert changed.value is True
    assert changed.evidence is None
    assert "I own a dog." not in _flat(client.get(URL))


@pytest.mark.postgres
def test_post_stores_typed_values(client, synced):
    client.post(URL, {**PET_PAGE, "license_date": "2026-02-01"})
    values = _values()
    assert values["pet_count"] == 2 and type(values["pet_count"]) is int
    assert values["licensed"] is True
    assert values["license_date"] == "2026-02-01"


@pytest.mark.postgres
def test_post_decimal_number_stores_a_float_and_prefills_it(client, synced):
    # The assistant may store a float; the page must round-trip it rather
    # than reject a value the litigant never typed.
    client.post(URL, {"pet_count": "2.5"})
    assert _values()["pet_count"] == 2.5
    assert 'value="2.5"' in _field_tag(_flat(client.get(URL)), "pet_count")


@pytest.mark.postgres
def test_resaving_an_untouched_float_keeps_its_stored_value(client, synced):
    # The form shows 1e-05 as "0.00001"; posting that back unchanged must
    # not rewrite the answer, and must still mark it reviewed.
    _store(client, "pet_count", 1e-05)
    client.post(URL, {**PET_PAGE, "pet_count": "0.00001"})
    assert _rows()["pet_count"] == (1e-05, True)


@pytest.mark.postgres
def test_number_field_takes_any_step_so_a_stored_decimal_resubmits(
    client, synced
):
    flat = _flat(client.get(URL))
    assert 'step="any"' in _field_tag(flat, "pet_count")
    assert "step=" not in _field_tag(flat, "full_name")


@pytest.mark.postgres
def test_reposting_updates_the_same_answer_row(client, synced):
    client.post(URL, {"pet_kind": "dog"})
    client.post(URL, {"pet_kind": "cat"})
    answer = VariableAnswer.objects.get()
    assert answer.value == "cat"
    assert answer.reviewed


@pytest.mark.postgres
def test_post_ignores_names_that_are_not_asked(client, synced):
    # vaccinated is gated on licensed=True, which is not stored yet, and
    # not_a_variable is a stray key.
    client.post(
        URL, {"pet_kind": "dog", "vaccinated": "true", "not_a_variable": "x"}
    )
    assert _values() == {"pet_kind": "dog"}


@pytest.mark.postgres
def test_post_accepts_a_gated_name_once_its_gate_is_stored(client, synced):
    client.post(URL, {"licensed": "true"})
    client.post(URL, {"licensed": "true", "vaccinated": "false"})
    assert _values() == {"licensed": True, "vaccinated": False}


def _briefcase_names(client):
    groups = client.get(URL).context["briefcase_groups"]
    return [a.variable.name for g in groups for a in g["answers"]]


@pytest.mark.postgres
def test_flipping_a_gate_on_a_later_save_clears_the_gated_answer(
    client, synced
):
    client.post(URL, {"licensed": "true"})
    client.post(URL, {"licensed": "true", "vaccinated": "true"})
    assert "vaccinated" in _briefcase_names(client)
    client.post(URL, {"licensed": "false"})
    assert _values() == {"licensed": False, "vaccinated": None}
    assert "vaccinated" not in _briefcase_names(client)


@pytest.mark.postgres
def test_flipping_a_gate_and_posting_the_gated_field_together_clears_it(
    client, synced
):
    client.post(URL, {"licensed": "true", "vaccinated": "true"})
    client.post(URL, {"licensed": "false", "vaccinated": "true"})
    assert _values() == {"licensed": False, "vaccinated": None}
    assert "vaccinated" not in _briefcase_names(client)


@pytest.mark.postgres
def test_an_unrelated_save_keeps_a_gated_fact_stored_before_its_gate(
    client, synced
):
    # The assistant may store a dependent before the gate is answered.
    _store(client, "vaccinated", True)
    client.post(URL, {"full_name": "Sandra Doe"})
    assert _values()["vaccinated"] is True


@pytest.mark.postgres
def test_post_empty_required_rerenders_in_place_with_aria_invalid(
    client, synced
):
    response = client.post(URL, {"first_name": "", "full_name": ""})
    assert response.status_code == 200
    assert re.search(
        r'name="full_name"[^>]*aria-invalid="true"', _flat(response)
    )
    assert not VariableAnswer.objects.exists()


@pytest.mark.postgres
def test_post_saves_valid_fields_even_when_a_sibling_is_invalid(
    client, synced
):
    response = client.post(URL, {**PET_PAGE, "pet_count": "two"})
    assert response.status_code == 200
    assert "Enter a number" in response.content.decode()
    assert _values() == {"pet_kind": "dog", "licensed": True}


@pytest.mark.postgres
def test_error_rerender_shows_a_field_gated_by_a_sibling_saved_in_the_same_post(
    client, synced
):
    # The re-render reads the answers back after the partial save, so the
    # gate that just landed decides which fields show beside the error.
    response = client.post(URL, {"licensed": "true", "pet_count": "two"})
    assert response.status_code == 200
    flat = _flat(response)
    assert _field_tag(flat, "vaccinated")
    assert re.search(r'name="pet_count"[^>]*aria-invalid="true"', flat)
    assert _values() == {"licensed": True}


@pytest.mark.postgres
def test_an_error_on_a_field_the_same_save_hides_is_dropped_not_lost(
    client, synced
):
    # The flipped gate hides vaccinated, so its error has nowhere to show;
    # the save lands and the page says so instead of reloading in silence.
    client.post(URL, {"licensed": "true"})
    response = client.post(
        URL, {"licensed": "false", "vaccinated": "maybe"}, follow=True
    )
    assert response.redirect_chain == [(f"{URL}#interview-2", 302)]
    assert "Saved." in response.content.decode()
    assert _values() == {"licensed": False}


@pytest.mark.postgres
def test_post_choice_outside_list_is_rejected_not_stored(client, synced):
    response = client.post(URL, {**PET_PAGE, "pet_kind": "bird"})
    assert response.status_code == 200
    assert "bird" not in response.content.decode()
    assert "pet_kind" not in _values()


@pytest.mark.postgres
def test_post_unparseable_date_soft_gates_instead_of_erroring(client, synced):
    response = client.post(URL, {"license_date": "01/02/2026"})
    assert response.status_code == 200
    assert re.search(
        r'name="license_date"[^>]*aria-invalid="true"', _flat(response)
    )
    assert not VariableAnswer.objects.exists()


@pytest.mark.postgres
def test_post_nan_number_soft_gates_instead_of_erroring(client, synced):
    # float("nan") parses, and Postgres rejects NaN in jsonb: without the
    # whole-digits rule this POST was a 500, not an inline error.
    response = client.post(URL, {"pet_count": "nan"})
    assert response.status_code == 200
    assert re.search(
        r'name="pet_count"[^>]*aria-invalid="true"', _flat(response)
    )
    assert not VariableAnswer.objects.exists()


@pytest.mark.postgres
def test_post_overflowing_decimal_soft_gates_instead_of_erroring(
    client, synced
):
    # Matches the digits rule, but float() gives inf, which Postgres
    # rejects in jsonb.
    response = client.post(URL, {"pet_count": "9" * 400 + ".0"})
    assert response.status_code == 200
    assert re.search(
        r'name="pet_count"[^>]*aria-invalid="true"', _flat(response)
    )
    assert not VariableAnswer.objects.exists()


@pytest.mark.postgres
def test_post_persists_stripped_value(client, synced):
    client.post(URL, {"full_name": "  Jane Doe ", "first_name": ""})
    assert _values() == {"full_name": "Jane Doe"}


@pytest.mark.postgres
def test_posted_answers_prefill_on_the_redirected_get(client, synced):
    client.post(URL, PET_PAGE)
    flat = _flat(client.get(URL))
    assert re.search(r'<option value="dog"[^>]*selected', flat)
    assert re.search(r'<option value="true"[^>]*selected', flat)
    assert 'value="2"' in _field_tag(flat, "pet_count")


@pytest.mark.postgres
def test_blank_protected_field_keeps_the_stored_answer(client, synced):
    client.post(URL, {"first_name": "Sandra", "full_name": "Sandra Doe"})
    client.post(URL, {"first_name": "", "full_name": "Sandra Roe"})
    assert _values() == {"first_name": "Sandra", "full_name": "Sandra Roe"}


@pytest.mark.postgres
def test_a_stored_protected_field_renders_without_required(client, synced):
    # It renders blank whatever is stored, so `required` would make the
    # browser refuse every later save of the page.
    assert re.search(
        r"\brequired\b", _field_tag(_flat(client.get(URL)), "first_name")
    )
    client.post(URL, {"first_name": "Sandra", "full_name": "Sandra Doe"})
    assert not re.search(
        r"\brequired\b", _field_tag(_flat(client.get(URL)), "first_name")
    )


@pytest.mark.postgres
def test_blank_protected_field_keeps_an_unreviewed_answer_unreviewed(
    client, synced
):
    _store(client, "first_name", "Sandra", reviewed=False)
    client.post(URL, {"first_name": "", "full_name": "Sandra Doe"})
    assert _rows()["first_name"] == ("Sandra", False)


@pytest.mark.postgres
def test_typing_a_protected_field_overwrites_it_and_marks_it_reviewed(
    client, synced
):
    # Overwriting is the only correction available for a field the page
    # can't show, so it has to work.
    _store(client, "first_name", "Sandra", reviewed=False)
    client.post(URL, {"first_name": "Alex", "full_name": "Alex Doe"})
    assert _rows()["first_name"] == ("Alex", True)


@pytest.mark.postgres
def test_checking_clear_erases_a_protected_answer(client, synced):
    client.post(URL, {"first_name": "Sandra", "full_name": "Sandra Doe"})
    client.post(
        URL,
        {"first_name": "", "first_name__clear": "on", "full_name": "S. Doe"},
    )
    assert _values()["first_name"] is None


@pytest.mark.postgres
def test_clearing_erases_an_unreviewed_assistant_answer_too(client, synced):
    _store(client, "first_name", "Sandra", reviewed=False)
    client.post(
        URL,
        {"first_name": "", "first_name__clear": "on", "full_name": "S. Doe"},
    )
    assert _values()["first_name"] is None


@pytest.mark.postgres
def test_a_typed_value_wins_over_the_clear_checkbox(client, synced):
    client.post(URL, {"first_name": "Sandra", "full_name": "Sandra Doe"})
    client.post(
        URL,
        {"first_name": "Alex", "first_name__clear": "on", "full_name": "A."},
    )
    assert _values()["first_name"] == "Alex"


@pytest.mark.postgres
def test_blank_optional_field_clears_its_answer(client, synced):
    client.post(URL, PET_PAGE)
    client.post(URL, {**PET_PAGE, "pet_count": ""})
    assert _values()["pet_count"] is None


@pytest.mark.postgres
def test_a_cleared_field_stays_blank_instead_of_showing_its_default(
    client, synced
):
    # Otherwise the next save of the page posts the default back as a
    # reviewed fact the litigant had removed.
    client.post(URL, PET_PAGE)
    client.post(URL, {**PET_PAGE, "pet_kind": ""})
    assert _values()["pet_kind"] is None
    flat = _flat(client.get(URL))
    assert not re.search(r'<option value="cat"[^>]*selected', flat)


# --- toasts -----------------------------------------------------------------


@pytest.mark.postgres
def test_post_save_flashes_a_saved_toast(client, synced):
    html = client.post(URL, PET_PAGE, follow=True).content.decode()
    assert "Saved." in html
    assert "For your privacy" not in html


@pytest.mark.postgres
def test_post_of_a_protected_answer_explains_the_privacy_blank(client, synced):
    response = client.post(
        URL, {"first_name": "Sandra", "full_name": "Sandra Doe"}, follow=True
    )
    assert "For your privacy" in response.content.decode()


@pytest.mark.postgres
def test_a_save_that_reveals_a_question_says_so_in_the_toast(client, synced):
    html = client.post(URL, {"licensed": "true"}, follow=True).content.decode()
    assert "More questions appeared" in html
    html = client.post(
        URL, {"licensed": "false"}, follow=True
    ).content.decode()
    assert "Saved." in html
    assert "More questions appeared" not in html


@pytest.mark.postgres
def test_the_gate_question_carries_the_more_questions_hint(client, synced):
    flat = _flat(client.get(URL))
    assert re.search(
        r'<p id="licensed-help"[^>]*>[^<]*more questions may appear', flat
    )
    assert not re.search(r'<p id="pet_kind-help"', flat)


@pytest.mark.postgres
def test_post_with_errors_flashes_no_toast(client, synced):
    response = client.post(URL, {"license_date": "not-a-date"})
    assert "Saved." not in response.content.decode()
