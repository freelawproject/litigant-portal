"""Tests for ``topic_flow/rows.py``: the guided page built from TopicFlow
rows (#1016).

Every test here is DB-free and runs in the fast suite: rows are unsaved
model instances built in memory. The view tests that drive these through
the page live in ``test_topic_flow_rows_view.py``.
"""

import pytest

from litigant_portal.app.models import (
    TopicFlow,
    TopicFlowInterviewPage,
    TopicFlowSection,
    Variable,
)
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.selectors.corpus import LAYOUT_BLOCKS
from litigant_portal.app.topic_flow import rows
from litigant_portal.app.topic_flow.renderer import RenderedSection

FACT_GATHER = "cotton/molecules/flow_section_fact_gather.html"


def _section(key, heading="Heading", content="Body."):
    return TopicFlowSection(key=key, heading=heading, content=content)


def _variable(name, **fields):
    return Variable(name=name, **{"label": name.replace("_", " "), **fields})


SECTIONS = [
    _section("overview", "Overview", "Read this first."),
    _section("fees", "Fees", "Pay the fee."),
]

PET_CHOICES = [
    {"value": "dog", "label": "Dog"},
    {"value": "cat", "label": "Cat"},
]
FULL_NAME = _variable("full_name", required=True)
PET_KIND = _variable(
    "pet_kind", data_type=VariableDataType.CHOICE, choices=PET_CHOICES
)
LICENSED = _variable("licensed", data_type=VariableDataType.BOOLEAN)
VACCINATED = _variable(
    "vaccinated",
    data_type=VariableDataType.BOOLEAN,
    asked_when=LICENSED,
    asked_when_value=True,
)


# --- layout -----------------------------------------------------------------


def test_layout_falls_back_to_sections_then_blocks_when_empty():
    flow = TopicFlow(layout=[])
    assert rows.flow_layout(flow, SECTIONS) == [
        "overview",
        "fees",
        *LAYOUT_BLOCKS,
    ]


def test_layout_is_used_as_stored_when_present():
    layout = ["packet", "fees", "interview", "overview"]
    flow = TopicFlow(layout=layout)
    assert rows.flow_layout(flow, SECTIONS) == layout


# --- render_flow ------------------------------------------------------------


def test_render_flow_gives_one_info_section_per_key_in_layout_order():
    flow = TopicFlow(layout=["fees", "overview"])
    rendered = rows.render_flow(flow, SECTIONS, [], {})
    assert all(isinstance(r, RenderedSection) for r in rendered)
    assert [r.anchor_id for r in rendered] == ["fees", "overview"]
    assert [r.heading for r in rendered] == ["Fees", "Overview"]
    assert [r.context["body"] for r in rendered] == [
        "Pay the fee.",
        "Read this first.",
    ]
    assert rendered[0].template == "cotton/molecules/flow_section_info.html"


def test_render_flow_gives_a_placeholder_per_block():
    flow = TopicFlow(layout=["overview", *LAYOUT_BLOCKS])
    rendered = rows.render_flow(flow, SECTIONS[:1], [], {})
    blocks = rendered[1:]
    placeholders = [name for name in LAYOUT_BLOCKS if name != "interview"]
    assert [r.anchor_id for r in blocks] == placeholders
    assert [r.heading for r in blocks] == [
        rows.BLOCK_HEADINGS[name] for name in placeholders
    ]
    assert all(
        r.template == "cotton/molecules/flow_section_placeholder.html"
        for r in blocks
    )


def test_interview_block_expands_to_one_section_per_page_in_order():
    flow = TopicFlow(layout=["interview", "overview"])
    pages = [
        (TopicFlowInterviewPage(title="About you", description="Who."), []),
        (TopicFlowInterviewPage(title="Your pet"), [PET_KIND]),
    ]
    rendered = rows.render_flow(flow, SECTIONS[:1], pages, {})
    assert [r.anchor_id for r in rendered] == [
        "interview-1",
        "interview-2",
        "overview",
    ]
    assert [r.heading for r in rendered[:2]] == ["About you", "Your pet"]
    assert all(r.template == FACT_GATHER for r in rendered[:2])
    assert rendered[0].context["description"] == "Who."
    assert [q["id"] for q in rendered[1].context["questions"]] == ["pet_kind"]


def test_section_without_a_key_gets_a_positional_anchor():
    # The schema requires a key, but an older or admin-edited row may lack
    # one; an empty id would send the left-region link to the page top.
    sections = [*SECTIONS, _section("", "Untitled", "Anything.")]
    assert rows.flow_layout(TopicFlow(layout=[]), sections)[:3] == [
        "overview",
        "fees",
        "section-3",
    ]
    rendered = rows.render_flow(TopicFlow(layout=[]), sections, [], {})
    assert rendered[2].anchor_id == "section-3"
    assert rendered[2].heading == "Untitled"


def test_render_flow_leaves_out_a_layout_name_the_schema_would_reject():
    # Only an admin edit to the layout column can get here; a 500 for every
    # visitor is the wrong answer to a typo.
    flow = TopicFlow(layout=["overview", "stray", "packet"])
    rendered = rows.render_flow(flow, SECTIONS[:1], [], {})
    assert [r.anchor_id for r in rendered] == ["overview", "packet"]


# --- gating -----------------------------------------------------------------


def test_ungated_variable_is_always_asked():
    assert LICENSED.is_asked({}) is True


def test_gated_variable_is_asked_only_when_the_gate_answer_matches():
    assert VACCINATED.is_asked({"licensed": True}) is True
    assert VACCINATED.is_asked({"licensed": False}) is False


def test_gated_variable_is_hidden_while_the_gate_is_unanswered():
    assert VACCINATED.is_asked({}) is False


def test_page_questions_leave_out_a_gated_variable_until_its_gate_is_met():
    placed = [LICENSED, VACCINATED]
    assert [q["id"] for q in rows.page_questions(placed, {})] == ["licensed"]
    asked = rows.page_questions(placed, {"licensed": True})
    assert [q["id"] for q in asked] == ["licensed", "vaccinated"]


def test_a_gate_question_says_more_questions_may_appear_after_saving():
    questions = {
        q["id"]: q
        for q in rows.page_questions(
            [LICENSED, VACCINATED, PET_KIND], {"licensed": True}, {"licensed"}
        )
    }
    assert questions["licensed"]["help_text"] == rows.GATE_HINT
    assert questions["vaccinated"]["help_text"] == ""
    assert questions["pet_kind"]["help_text"] == ""


def test_the_gate_hint_follows_the_gate_questions_own_help_text():
    gate = _variable(
        "licensed", data_type=VariableDataType.BOOLEAN, help_text="Yes or no."
    )
    gated = _variable("vaccinated", asked_when=gate, asked_when_value=True)
    (question,) = rows.page_questions([gate, gated], {}, {"licensed"})
    assert question["help_text"] == f"Yes or no. {rows.GATE_HINT}"


def test_gate_names_spans_every_page():
    pages = [
        (TopicFlowInterviewPage(title="A"), [LICENSED]),
        (TopicFlowInterviewPage(title="B"), [VACCINATED, PET_KIND]),
    ]
    assert rows.gate_names(pages) == {"licensed"}


def test_a_gate_on_an_earlier_page_than_its_dependents_still_carries_the_hint():
    flow = TopicFlow(layout=["interview"])
    pages = [
        (TopicFlowInterviewPage(title="A"), [LICENSED]),
        (TopicFlowInterviewPage(title="B"), [VACCINATED]),
    ]
    first, _second = rows.render_flow(flow, [], pages, {})
    (question,) = first.context["questions"]
    assert question["help_text"] == rows.GATE_HINT


def test_asked_names_spans_every_page():
    pages = [
        (TopicFlowInterviewPage(title="A"), [FULL_NAME]),
        (TopicFlowInterviewPage(title="B"), [LICENSED, VACCINATED]),
    ]
    assert rows.asked_names(pages, {}) == ["full_name", "licensed"]
    assert rows.asked_names(pages, {"licensed": True}) == [
        "full_name",
        "licensed",
        "vaccinated",
    ]


GATED_PAGES = [
    (TopicFlowInterviewPage(title="A"), [FULL_NAME]),
    (TopicFlowInterviewPage(title="B"), [LICENSED, VACCINATED]),
]


@pytest.mark.parametrize(
    ("answers", "valid", "stale"),
    [
        (
            {"licensed": True, "vaccinated": True},
            {"licensed": False},
            ["vaccinated"],
        ),
        (
            {"licensed": True, "vaccinated": True},
            {"licensed": False, "vaccinated": False},
            ["vaccinated"],
        ),
        ({"licensed": True, "vaccinated": True}, {"full_name": "Sam"}, []),
        ({"licensed": True}, {"licensed": False}, []),
        ({"licensed": False, "vaccinated": None}, {"full_name": "Sam"}, []),
    ],
    ids=[
        "gate-flipped-clears-the-stored-gated-answer",
        "gate-flipped-and-gated-field-posted-together-clears-it",
        "gate-unchanged-leaves-it-alone",
        "gated-variable-with-no-answer-is-not-listed",
        "already-cleared-gated-answer-is-not-listed",
    ],
)
def test_stale_gated_names_lists_answers_whose_gate_stops_matching(
    answers, valid, stale
):
    assert rows.stale_gated_names(GATED_PAGES, answers, valid) == stale


# --- questions --------------------------------------------------------------


def _question(variable, answers=None):
    (question,) = rows.page_questions([variable], answers or {})
    return question


@pytest.mark.parametrize(
    ("data_type", "expected"),
    [
        (VariableDataType.TEXT, "text"),
        (VariableDataType.DATE, "date"),
        (VariableDataType.DATETIME, "datetime-local"),
        (VariableDataType.NUMBER, "number"),
        (VariableDataType.CHOICE, "choice"),
        (VariableDataType.BOOLEAN, "boolean"),
    ],
    ids=[
        "text-is-text-input",
        "date-is-date-input",
        "datetime-is-datetime-local-input",
        "number-is-number-input",
        "choice-is-select",
        "boolean-is-yes-no-select",
    ],
)
def test_question_type_follows_the_data_type(data_type, expected):
    question = _question(_variable("fact", data_type=data_type))
    assert question["type"] == expected


def test_number_question_takes_any_step_and_the_others_take_none():
    number = _variable("count", data_type=VariableDataType.NUMBER)
    assert _question(number)["step"] == "any"
    assert _question(FULL_NAME)["step"] == ""


def test_question_carries_the_glossary_metadata():
    question = _question(
        _variable(
            "pet_kind",
            label="Kind of pet",
            help_text="Dogs and cats only.",
            data_type=VariableDataType.CHOICE,
            choices=PET_CHOICES,
        )
    )
    assert question["label"] == "Kind of pet"
    assert question["help_text"] == "Dogs and cats only."
    assert question["required"] is False
    assert question["choices"] == PET_CHOICES


def test_boolean_question_offers_yes_and_no():
    question = _question(LICENSED)
    assert [c["value"] for c in question["choices"]] == ["true", "false"]
    assert [str(c["label"]) for c in question["choices"]] == ["Yes", "No"]


def test_question_value_prefers_the_stored_answer_over_the_default():
    variable = _variable(
        "pet_kind",
        data_type=VariableDataType.CHOICE,
        choices=PET_CHOICES,
        default="cat",
    )
    assert _question(variable, {"pet_kind": "dog"})["value"] == "dog"


def test_question_value_falls_back_to_the_default():
    variable = _variable(
        "pet_kind",
        data_type=VariableDataType.CHOICE,
        choices=PET_CHOICES,
        default="cat",
    )
    assert _question(variable)["value"] == "cat"
    assert _question(PET_KIND)["value"] == ""


@pytest.mark.parametrize(
    ("stored", "expected"),
    [(True, "true"), (False, "false"), (3, "3"), ("2026-03-15", "2026-03-15")],
    ids=["true", "false", "number", "date"],
)
def test_question_value_is_the_form_string_of_the_stored_answer(
    stored, expected
):
    variable = _variable("fact")
    assert _question(variable, {"fact": stored})["value"] == expected


def test_protected_question_renders_blank_and_marks_saved():
    first_name = _variable("first_name")
    question = _question(first_name, {"first_name": "Sandra"})
    assert question["value"] == ""
    assert question["saved"] is True
    assert _question(first_name)["saved"] is False


def test_a_stored_protected_field_drops_required_since_it_renders_blank():
    first_name = _variable("first_name", required=True)
    assert _question(first_name)["required"] is True
    assert _question(first_name, {"first_name": "Sandra"})["required"] is False


# --- coercion ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("data_type", "raw", "expected"),
    [
        (VariableDataType.TEXT, "  Jane ", "Jane"),
        (VariableDataType.TEXT, "   ", None),
        (VariableDataType.NUMBER, " 3 ", 3),
        (VariableDataType.NUMBER, "7", 7),
        (VariableDataType.NUMBER, " -3 ", -3),
        (VariableDataType.NUMBER, "2.5", 2.5),
        (VariableDataType.BOOLEAN, "true", True),
        (VariableDataType.BOOLEAN, "false", False),
        (VariableDataType.DATE, "2026-02-01", "2026-02-01"),
        (VariableDataType.CHOICE, "dog ", "dog"),
    ],
    ids=[
        "text-strips",
        "blank-is-none",
        "number-int",
        "number-digits",
        "number-negative",
        "number-decimal",
        "boolean-true",
        "boolean-false",
        "date-stays-string",
        "choice-strips",
    ],
)
def test_coerce_value(data_type, raw, expected):
    value = rows.coerce_value(_variable("fact", data_type=data_type), raw)
    assert value == expected
    assert type(value) is type(expected)


@pytest.mark.parametrize(
    ("data_type", "raw"),
    [
        (VariableDataType.NUMBER, "ten"),
        (VariableDataType.NUMBER, "2."),
        (VariableDataType.NUMBER, "nan"),
        (VariableDataType.NUMBER, "inf"),
        (VariableDataType.NUMBER, "1_000"),
        (VariableDataType.NUMBER, "1e3"),
        (VariableDataType.BOOLEAN, "maybe"),
    ],
    ids=[
        "number-rejects-letters",
        "number-rejects-a-trailing-point",
        "number-rejects-nan",
        "number-rejects-inf",
        "number-rejects-underscores",
        "number-rejects-exponent",
        "boolean-rejects-other",
    ],
)
def test_coerce_value_rejects_what_the_type_cannot_hold(data_type, raw):
    with pytest.raises(ValueError):
        rows.coerce_value(_variable("fact", data_type=data_type), raw)


# --- validation -------------------------------------------------------------

COUNT = _variable("pet_count", data_type=VariableDataType.NUMBER)
LICENSE_DATE = _variable("license_date", data_type=VariableDataType.DATE)
VARIABLES = [FULL_NAME, PET_KIND, LICENSED, COUNT, LICENSE_DATE]


@pytest.mark.parametrize(
    ("submitted", "expected"),
    [
        ({"full_name": "  "}, {"full_name": [rows.REQUIRED_ERROR]}),
        ({"pet_kind": ""}, {}),
        ({"pet_kind": "bird"}, {"pet_kind": [rows.INVALID_CHOICE_ERROR]}),
        ({"pet_kind": " dog "}, {}),
        (
            {"license_date": "01/02/2026"},
            {"license_date": [rows.INVALID_DATE_ERROR]},
        ),
        ({"license_date": "2026-02-01"}, {}),
        ({"pet_count": "ten"}, {"pet_count": [rows.INVALID_NUMBER_ERROR]}),
        ({"pet_count": "2"}, {}),
        ({"licensed": "maybe"}, {"licensed": [rows.INVALID_CHOICE_ERROR]}),
        ({"pet_kind": "dog"}, {}),
    ],
    ids=[
        "required-blank-errors",
        "optional-blank-ok",
        "choice-outside-list-errors",
        "choice-is-checked-stripped",
        "bad-date-errors",
        "iso-date-ok",
        "bad-number-errors",
        "number-ok",
        "bad-boolean-errors",
        "not-submitted-is-skipped",
    ],
)
def test_validate_answers(submitted, expected):
    # The last case leaves the required full_name out of the submission: a
    # field from a page that was not posted is not an error.
    assert rows.validate_answers(VARIABLES, submitted) == expected


def test_a_blank_kept_protected_field_is_not_a_missing_required_answer():
    first_name = _variable("first_name", required=True)
    blank = {"first_name": ""}
    assert rows.validate_answers([first_name], blank) == {
        "first_name": [rows.REQUIRED_ERROR]
    }
    assert rows.validate_answers([first_name], blank, {"first_name"}) == {}


# --- redirect anchor --------------------------------------------------------


def test_submitted_section_anchor_names_the_owning_page():
    pages = [
        (TopicFlowInterviewPage(title="A"), [FULL_NAME]),
        (TopicFlowInterviewPage(title="B"), [PET_KIND, LICENSED]),
    ]
    assert rows.submitted_section_anchor(pages, ["licensed"]) == "interview-2"
    assert rows.submitted_section_anchor(pages, ["full_name"]) == "interview-1"
    assert rows.submitted_section_anchor(pages, ["stray"]) is None


# --- errors on the re-render ------------------------------------------------


def test_errors_land_on_their_question_and_focus_the_first_invalid_one():
    flow = TopicFlow(layout=["interview"])
    pages = [(TopicFlowInterviewPage(title="A"), [FULL_NAME, PET_KIND])]
    errors = {"pet_kind": [rows.INVALID_CHOICE_ERROR]}
    (section,) = rows.render_flow(flow, [], pages, {}, errors)
    full_name, pet_kind = section.context["questions"]
    assert full_name["errors"] == [] and full_name["autofocus"] is False
    assert pet_kind["errors"] == [rows.INVALID_CHOICE_ERROR]
    assert pet_kind["autofocus"] is True
