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

from litigant_portal.app.models import UserIdentity, Variable, VariableAnswer
from litigant_portal.app.selectors import corpus as selectors
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
            "default": "cat",
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
    corpus = _corpus()
    with mock.patch.object(services, "corpus_load", return_value=corpus):
        corpus_sync()
    # The view's court check reads the topic index from disk; keep it on
    # the fake corpus so ``alpha`` is a known court for every test here.
    with mock.patch.object(
        selectors, "corpus_load_topics", return_value=corpus.topics
    ):
        yield


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
    # The input stays blank (the briefcase panel may still list the fact).
    field = _field_tag(after, "first_name")
    assert field and "Sandra" not in field
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
def test_corpus_source_404s_a_court_the_corpus_lacks_when_corpus_court_is_unset(
    client, synced
):
    assert client.get(URL).status_code == 200
    assert client.get(f"/t/beta/{TOPIC}/{ROLE}/").status_code == 404


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
            ),
            FactGatherSection(
                kind="fact_gather",
                id="facts",
                heading="Your facts",
                questions=[Question(id="filing_county", label="County")],
            ),
        ],
    )
    monkeypatch.setattr(pages.registry, "get", lambda *a: registry_corpus)
    response = client.get(URL)
    assert response.context["page_title"] == "From YAML"
    flat = _flat(response)
    assert _section_ids(flat) == ["intro", "facts"]
    # The shared form names itself by the heading on this path too.
    assert re.search(r'<form[^>]*aria-labelledby="facts-heading"', flat)

    monkeypatch.setattr(pages.registry, "get", lambda *a: None)
    assert client.get(URL).status_code == 404


# --- identity ---------------------------------------------------------------


@pytest.mark.postgres
def test_corpus_source_first_time_visitor_creates_no_identity(client, synced):
    assert client.get(URL).status_code == 200
    assert UserIdentity.objects.count() == 0


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
    client.post(URL, PET_PAGE)
    assert all(reviewed for _value, reviewed in _rows().values())


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
def test_number_field_takes_any_step_so_a_stored_decimal_resubmits(
    client, synced
):
    flat = _flat(client.get(URL))
    assert 'step="any"' in _field_tag(flat, "pet_count")
    assert "step=" not in _field_tag(flat, "full_name")


@pytest.mark.postgres
def test_post_writes_the_same_rows_the_content_path_writes(
    client, synced, settings, monkeypatch
):
    # DoD item 2: one submission, both page sources, identical rows. Shaped
    # like the ND flow: a text, a choice and a date answer.
    answers = {
        "full_name": "Jane Doe",
        "pet_kind": "dog",
        "license_date": "2026-02-01",
    }
    client.post(URL, answers)
    from_rows = _rows()
    VariableAnswer.objects.all().delete()

    settings.TOPIC_FLOW_SOURCE = "content"
    registry_corpus = Corpus(
        metadata=Metadata(court=COURT, topic=TOPIC, role=ROLE, title="T"),
        sections=[
            FactGatherSection(
                kind="fact_gather",
                id="facts",
                heading="Facts",
                questions=[
                    Question(id="full_name", label="Full name"),
                    Question(
                        id="pet_kind",
                        label="Kind",
                        type="choice",
                        choices=["dog", "cat"],
                    ),
                    Question(id="license_date", label="When", type="date"),
                ],
            )
        ],
    )
    monkeypatch.setattr(pages.registry, "get", lambda *a: registry_corpus)
    client.post(URL, answers)
    assert _rows() == from_rows
    assert from_rows == {
        name: (value, True) for name, value in answers.items()
    }


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
def test_blank_protected_field_keeps_an_unreviewed_answer_unreviewed(
    client, synced
):
    _store(client, "first_name", "Sandra", reviewed=False)
    client.post(URL, {"first_name": "", "full_name": "Sandra Doe"})
    assert _rows()["first_name"] == ("Sandra", False)


@pytest.mark.postgres
def test_checking_clear_erases_a_protected_answer(client, synced):
    client.post(URL, {"first_name": "Sandra", "full_name": "Sandra Doe"})
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
