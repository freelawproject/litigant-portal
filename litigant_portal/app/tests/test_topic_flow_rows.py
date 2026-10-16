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


# --- gating -----------------------------------------------------------------


def test_ungated_variable_is_always_asked():
    assert rows.is_asked(LICENSED, {}) is True


def test_gated_variable_is_asked_only_when_the_gate_answer_matches():
    assert rows.is_asked(VACCINATED, {"licensed": True}) is True
    assert rows.is_asked(VACCINATED, {"licensed": False}) is False


def test_gated_variable_is_hidden_while_the_gate_is_unanswered():
    assert rows.is_asked(VACCINATED, {}) is False


def test_page_questions_leave_out_a_gated_variable_until_its_gate_is_met():
    placed = [LICENSED, VACCINATED]
    assert [q["id"] for q in rows.page_questions(placed, {})] == ["licensed"]
    asked = rows.page_questions(placed, {"licensed": True})
    assert [q["id"] for q in asked] == ["licensed", "vaccinated"]


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
