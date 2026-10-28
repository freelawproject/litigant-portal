"""Tests for ``topic_flow/rows.py``: the guided page built from TopicFlow
rows (#1016).

Every test here is DB-free and runs in the fast suite: rows are unsaved
model instances built in memory. The view tests that drive these through
the page live in ``test_topic_flow_rows_view.py``.
"""

from datetime import date

import pytest

from litigant_portal.app.models import (
    Contact,
    Form,
    Resource,
    TopicFlow,
    TopicFlowDeadline,
    TopicFlowFormCondition,
    TopicFlowInterviewPage,
    TopicFlowSection,
    Variable,
)
from litigant_portal.app.models.choices import (
    TopicFlowFormConditionOperator,
    VariableDataType,
)
from litigant_portal.app.selectors.corpus import LAYOUT_BLOCKS
from litigant_portal.app.topic_flow import rows
from litigant_portal.app.topic_flow.rows import RenderedSection

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


# --- contacts and resources blocks ------------------------------------------

URL_PARTS = {"court": "alpha", "topic": "pets", "role": "standard"}
CONTACTS = [
    Contact(key="clerk", name="Clerk of Court", phone="555-1234"),
    Contact(key="aid", name="Legal Aid", hours="9-4 M-F"),
]
RESOURCES = [
    Resource(key="self-help", label="Self Help", url="https://help.example"),
    Resource(
        key="rules", label="Rules", url="https://rules.example", note="Ch. 3"
    ),
]


def test_render_flow_lists_court_resources_under_the_resources_block():
    flow = TopicFlow(layout=["resources"])
    (section,) = rows.render_flow(
        flow, [], [], {}, resources=RESOURCES, **URL_PARTS
    )
    assert section.anchor_id == "resources"
    assert section.heading == rows.BLOCK_HEADINGS["resources"]
    assert section.template == "cotton/molecules/flow_section_resources.html"
    assert section.context == {
        "resources": [
            {
                "id": "self-help",
                "label": "Self Help",
                "url": "https://help.example",
                "note": "",
            },
            {
                "id": "rules",
                "label": "Rules",
                "url": "https://rules.example",
                "note": "Ch. 3",
            },
        ]
    }


def test_render_flow_lists_court_contacts_with_the_download_id():
    flow = TopicFlow(layout=["contacts"])
    (section,) = rows.render_flow(
        flow, [], [], {}, contacts=CONTACTS, **URL_PARTS
    )
    assert section.anchor_id == "contacts"
    assert section.heading == rows.BLOCK_HEADINGS["contacts"]
    assert section.template == "cotton/molecules/flow_section_vcf.html"
    assert [c["id"] for c in section.context["contacts"]] == ["clerk", "aid"]
    assert section.context["contacts"][1]["hours"] == "9-4 M-F"
    assert {k: section.context[k] for k in ("court", "topic", "role")} == (
        URL_PARTS
    )
    assert section.context["output_id"] == "contacts"


@pytest.mark.parametrize(
    "row",
    [
        Contact(name="Bailiff"),
        Resource(label="Statutes", url="https://law.example"),
        TopicFlowDeadline(label="Answer due"),
    ],
    ids=["contact", "resource", "deadline"],
)
def test_a_row_without_a_key_is_referenced_by_its_id(row):
    # A row synced before keys existed and adopted by no authored entry
    # keeps a blank key; the vCard and calendar UIDs must still be distinct.
    assert row.ref == str(row.pk)
    row.key = "clerk"
    assert row.ref == "clerk"


def test_render_flow_skips_contacts_and_resources_blocks_when_empty():
    flow = TopicFlow(layout=["overview", "contacts", "resources"])
    rendered = rows.render_flow(flow, SECTIONS[:1], [], {}, **URL_PARTS)
    assert [r.anchor_id for r in rendered] == ["overview"]


# --- packet -----------------------------------------------------------------

PETITION = Form(
    slug="petition", name="Petition", url="https://x.example/p.pdf"
)
CHECKLIST = Form(slug="checklist", name="Checklist")
WAIVER = Form(slug="waiver", name="Fee waiver")


def _condition(form, variable=None, operator="equals", value=None):
    return TopicFlowFormCondition(
        form=form,
        variable=variable,
        operator=TopicFlowFormConditionOperator(operator),
        value=value,
    )


@pytest.mark.parametrize(
    ("condition", "answers", "holds"),
    [
        (_condition(PETITION), {}, True),
        (
            _condition(WAIVER, LICENSED, "equals", True),
            {"licensed": True},
            True,
        ),
        (
            _condition(WAIVER, LICENSED, "equals", True),
            {"licensed": False},
            False,
        ),
        (_condition(WAIVER, LICENSED, "equals", True), {}, False),
        (
            _condition(WAIVER, LICENSED, "not_equals", True),
            {"licensed": False},
            True,
        ),
        (_condition(WAIVER, LICENSED, "not_equals", True), {}, True),
        (
            _condition(WAIVER, LICENSED, "not_equals", True),
            {"licensed": True},
            False,
        ),
    ],
    ids=[
        "no-variable-always",
        "equals-matches",
        "equals-other-value",
        "equals-unanswered",
        "not-equals-other-value",
        "not-equals-unanswered",
        "not-equals-matching-value",
    ],
)
def test_form_condition_holds(condition, answers, holds):
    assert rows.form_condition_holds(condition, answers) is holds


def test_packet_forms_keep_order_and_drop_unmet_conditions():
    conditions = [
        _condition(CHECKLIST),
        _condition(WAIVER, LICENSED, "equals", True),
        _condition(PETITION),
    ]
    assert rows.packet_forms(conditions, {}) == [
        {"name": "Checklist", "url": ""},
        {"name": "Petition", "url": "https://x.example/p.pdf"},
    ]
    assert [
        f["name"] for f in rows.packet_forms(conditions, {"licensed": True})
    ] == [
        "Checklist",
        "Fee waiver",
        "Petition",
    ]


def test_render_flow_packet_lists_the_forms_without_an_interview_button():
    flow = TopicFlow(layout=["packet"])
    conditions = [_condition(PETITION), _condition(CHECKLIST)]
    (section,) = rows.render_flow(
        flow, [], [], {}, form_conditions=conditions, **URL_PARTS
    )
    assert section.anchor_id == "packet"
    assert section.heading == rows.BLOCK_HEADINGS["packet"]
    assert section.template == "cotton/molecules/flow_section_packet.html"
    assert section.context == {
        "forms": [
            {"name": "Petition", "url": "https://x.example/p.pdf"},
            {"name": "Checklist", "url": ""},
        ],
        "interview_available": False,
        **URL_PARTS,
    }


def test_packet_offers_the_interview_only_with_a_reference_and_a_docassemble(
    settings,
):
    # Same rule as the content renderer: both the row's reference and a
    # configured docassemble, else a plain form list.
    conditions = [_condition(PETITION)]
    with_reference = TopicFlow(
        layout=["packet"], interview_reference="docassemble.x:q.yml"
    )

    def available(flow):
        (section,) = rows.render_flow(
            flow, [], [], {}, form_conditions=conditions, **URL_PARTS
        )
        return section.context["interview_available"]

    settings.DOCASSEMBLE_BASE_URL = "https://da.example.gov/interview"
    settings.DOCASSEMBLE_PUBLIC_URL = None
    assert available(with_reference) is True
    assert available(TopicFlow(layout=["packet"])) is False
    settings.DOCASSEMBLE_BASE_URL = None
    assert available(with_reference) is False


def test_packet_with_a_handoff_renders_for_the_button_alone(settings):
    # Every form gated and unmet, but the interview still fills them, so
    # the block must not hide the button with the list.
    flow = TopicFlow(
        layout=["packet"], interview_reference="docassemble.x:q.yml"
    )
    gated = [_condition(WAIVER, LICENSED, "equals", True)]
    settings.DOCASSEMBLE_BASE_URL = "https://da.example.gov/interview"
    settings.DOCASSEMBLE_PUBLIC_URL = None
    (section,) = rows.render_flow(
        flow, [], [], {}, form_conditions=gated, **URL_PARTS
    )
    assert section.context["forms"] == []
    assert section.context["interview_available"] is True

    settings.DOCASSEMBLE_BASE_URL = None
    assert (
        rows.render_flow(flow, [], [], {}, form_conditions=gated, **URL_PARTS)
        == []
    )


def test_flow_variable_names_include_form_condition_variables():
    # The chat may store the answer a condition reads, and no page of this
    # flow asks it; the page must still read it to show the form.
    waiver_needed = _variable(
        "waiver_needed", data_type=VariableDataType.BOOLEAN
    )
    pages = [(TopicFlowInterviewPage(title="A"), [FULL_NAME, LICENSED])]
    conditions = [
        _condition(PETITION),
        _condition(WAIVER, waiver_needed, "equals", True),
        _condition(CHECKLIST, LICENSED, "equals", True),
    ]
    assert rows.flow_variable_names(pages, conditions) == [
        "full_name",
        "licensed",
        "waiver_needed",
    ]


def test_render_flow_skips_the_packet_block_without_forms():
    flow = TopicFlow(layout=["overview", "packet"])
    assert [
        r.anchor_id
        for r in rows.render_flow(flow, SECTIONS[:1], [], {}, **URL_PARTS)
    ] == ["overview"]
    # Every form conditional and unmet is the same as no forms at all.
    gated = [_condition(WAIVER, LICENSED, "equals", True)]
    assert [
        r.anchor_id
        for r in rows.render_flow(
            flow, SECTIONS[:1], [], {}, form_conditions=gated, **URL_PARTS
        )
    ] == ["overview"]


# --- calendar ---------------------------------------------------------------

LICENSE_DATE_VAR = _variable("license_date", data_type=VariableDataType.DATE)
RENEWAL = TopicFlowDeadline(
    key="renewal",
    label="License renewal due",
    description="One year on.",
    offset_days=365,
    offset_from=LICENSE_DATE_VAR,
)
INSPECTION = TopicFlowDeadline(
    key="inspection",
    label="Inspection",
    offset_days=30,
    offset_from=LICENSE_DATE_VAR,
)


def test_flow_deadlines_use_the_row_key_as_id_and_the_variable_name_as_source():
    resolved = rows.flow_deadlines(
        [RENEWAL, INSPECTION], {"license_date": "2026-02-01"}
    )
    assert resolved == [
        {
            "id": "renewal",
            "label": "License renewal due",
            "description": "One year on.",
            "date": date(2027, 2, 1),
        },
        {
            "id": "inspection",
            "label": "Inspection",
            "description": "",
            "date": date(2026, 3, 3),
        },
    ]
    assert [d["date"] for d in rows.flow_deadlines([RENEWAL], {})] == [None]


def test_render_flow_calendar_has_dates_only_once_a_date_is_stored():
    flow = TopicFlow(layout=["calendar"])
    (pending,) = rows.render_flow(
        flow, [], [], {}, deadlines=[RENEWAL], **URL_PARTS
    )
    assert pending.anchor_id == "calendar"
    assert pending.heading == rows.BLOCK_HEADINGS["calendar"]
    assert pending.template == "cotton/molecules/flow_section_ics.html"
    assert pending.context["has_dates"] is False
    assert pending.context["deadlines"] == [
        {
            "label": "License renewal due",
            "description": "One year on.",
            "date_display": None,
            "date_iso": None,
        }
    ]
    assert pending.context["output_id"] == "calendar"
    assert {k: pending.context[k] for k in ("court", "topic", "role")} == (
        URL_PARTS
    )

    (stored,) = rows.render_flow(
        flow,
        [],
        [],
        {"license_date": "2026-02-01"},
        deadlines=[RENEWAL],
        **URL_PARTS,
    )
    assert stored.context["has_dates"] is True
    assert stored.context["deadlines"][0]["date_iso"] == "2027-02-01"
    assert (
        stored.context["deadlines"][0]["date_display"]
        == "Monday, February 1, 2027"
    )


def test_render_flow_skips_the_calendar_block_without_deadlines():
    flow = TopicFlow(layout=["overview", "calendar"])
    rendered = rows.render_flow(flow, SECTIONS[:1], [], {}, **URL_PARTS)
    assert [r.anchor_id for r in rendered] == ["overview"]


def test_flow_variable_names_include_deadline_sources():
    # A deadline's source date may be stored by the chat and asked on no
    # page of this flow.
    pages = [(TopicFlowInterviewPage(title="A"), [FULL_NAME])]
    assert rows.flow_variable_names(
        pages, deadlines=[RENEWAL, INSPECTION]
    ) == [
        "full_name",
        "license_date",
    ]


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
    flow = TopicFlow(layout=["overview", "stray", "fees"])
    rendered = rows.render_flow(flow, SECTIONS, [], {})
    assert [r.anchor_id for r in rendered] == ["overview", "fees"]


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
        ({"vaccinated": True}, {"full_name": "Sam"}, []),
        ({"vaccinated": True}, {"licensed": True}, []),
        ({"vaccinated": True}, {"licensed": False}, ["vaccinated"]),
    ],
    ids=[
        "gate-flipped-clears-the-stored-gated-answer",
        "gate-flipped-and-gated-field-posted-together-clears-it",
        "gate-unchanged-leaves-it-alone",
        "gated-variable-with-no-answer-is-not-listed",
        "already-cleared-gated-answer-is-not-listed",
        "unanswered-gate-untouched-keeps-a-pre-stored-dependent",
        "unanswered-gate-now-matching-keeps-it",
        "unanswered-gate-now-mismatching-clears-it",
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


def test_question_text_is_asked_over_the_label_when_authored():
    variable = _variable(
        "convicted",
        label="Convicted",
        question="Have you ever been convicted of a crime?",
    )
    assert (
        _question(variable)["label"]
        == "Have you ever been convicted of a crime?"
    )


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


def test_a_cleared_answer_renders_blank_not_the_default():
    variable = _variable(
        "pet_kind",
        data_type=VariableDataType.CHOICE,
        choices=PET_CHOICES,
        default="cat",
    )
    (question,) = rows.page_questions([variable], {}, cleared={"pet_kind"})
    assert question["value"] == ""


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


@pytest.mark.parametrize(
    ("data_type", "stored", "expected"),
    [
        (VariableDataType.DATE, "20260315", "2026-03-15"),
        (VariableDataType.DATETIME, "2026-03-15T09:30:00", "2026-03-15T09:30"),
        (
            VariableDataType.DATETIME,
            "2026-03-15 09:30+02:00",
            "2026-03-15T09:30",
        ),
        (VariableDataType.DATETIME, "2026-03-15", "2026-03-15T00:00"),
    ],
    ids=[
        "date-basic-form",
        "datetime-seconds",
        "datetime-offset",
        "date-only",
    ],
)
def test_a_stored_date_renders_in_the_inputs_own_format(
    data_type, stored, expected
):
    # Another writer may store any ISO form the validator accepts; the
    # input shows only one, and a blank would be erased on the next save.
    variable = _variable("fact", data_type=data_type)
    assert _question(variable, {"fact": stored})["value"] == expected


@pytest.mark.parametrize(
    ("stored", "expected"),
    [(1e-05, "0.00001"), (1e20, "100000000000000000000"), (2.5, "2.5")],
    ids=["small", "large", "plain"],
)
def test_a_stored_float_renders_in_full_not_in_exponent_form(stored, expected):
    # str(1e-05) is "1e-05", which the number rule rejects on resubmit.
    variable = _variable("fact", data_type=VariableDataType.NUMBER)
    assert _question(variable, {"fact": stored})["value"] == expected


@pytest.mark.parametrize(
    ("data_type", "stored"),
    [
        (VariableDataType.DATE, "March 15, 2026"),
        (VariableDataType.DATE, ["2026-03-15"]),
        (VariableDataType.DATETIME, "yesterday"),
    ],
    ids=["date-prose", "date-not-a-string", "datetime-prose"],
)
def test_an_unparseable_stored_date_still_renders(data_type, stored):
    # Nothing re-validates stored answers when the glossary changes a
    # variable's type, so the page must not 500 on a value it can't parse.
    variable = _variable("fact", data_type=data_type)
    assert _question(variable, {"fact": stored})["value"] == str(stored)


def test_private_question_renders_blank_and_marks_saved():
    first_name = _variable("first_name", is_private=True)
    question = _question(first_name, {"first_name": "Sandra"})
    assert question["value"] == ""
    assert question["saved"] is True
    assert _question(first_name)["saved"] is False


def test_the_glossary_flag_decides_privacy_not_the_variable_name():
    # ``first_name`` is private in the real glossary; the page reads the row.
    first_name = _variable("first_name")
    assert _question(first_name, {"first_name": "Sandra"})["value"] == "Sandra"


def test_private_names_spans_every_page():
    dob = _variable("date_of_birth", is_private=True)
    pages = [("p1", [FULL_NAME]), ("p2", [dob, PET_KIND])]
    assert rows.private_names(pages) == {"date_of_birth"}


def test_a_stored_private_field_drops_required_since_it_renders_blank():
    first_name = _variable("first_name", required=True, is_private=True)
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
        (VariableDataType.NUMBER, "9" * 400 + ".0"),
        (VariableDataType.BOOLEAN, "maybe"),
    ],
    ids=[
        "number-rejects-letters",
        "number-rejects-a-trailing-point",
        "number-rejects-nan",
        "number-rejects-inf",
        "number-rejects-underscores",
        "number-rejects-exponent",
        "number-rejects-a-decimal-that-overflows",
        "boolean-rejects-other",
    ],
)
def test_coerce_value_rejects_what_the_type_cannot_hold(data_type, raw):
    with pytest.raises(ValueError):
        rows.coerce_value(_variable("fact", data_type=data_type), raw)


# --- unchanged answers ------------------------------------------------------

BY_NAME = {
    "when": _variable("when", data_type=VariableDataType.DATETIME),
    "pet_count": _variable("pet_count", data_type=VariableDataType.NUMBER),
    "secret": _variable("secret", is_private=True),
}


def _restored(submitted, answers):
    valid = {
        name: rows.coerce_value(BY_NAME[name], raw)
        for name, raw in submitted.items()
    }
    return rows.restore_unchanged(BY_NAME, submitted, answers, valid)


def test_an_unchanged_datetime_re_saves_its_stored_zone_and_seconds():
    stored = {"when": "2026-03-15T15:00:00+00:00"}
    assert _restored({"when": "2026-03-15T15:00"}, stored) == stored


def test_an_unchanged_float_re_saves_its_stored_type():
    assert _restored({"pet_count": "2.5"}, {"pet_count": 2.5}) == {
        "pet_count": 2.5
    }
    assert _restored({"pet_count": "2"}, {"pet_count": 2.0}) == {
        "pet_count": 2
    }


def test_a_changed_value_is_written_as_posted():
    stored = {"when": "2026-03-15T15:00:00+00:00"}
    assert _restored({"when": "2026-03-16T15:00"}, stored) == {
        "when": "2026-03-16T15:00"
    }


def test_a_first_answer_is_written_as_posted():
    assert _restored({"when": "2026-03-15T15:00"}, {}) == {
        "when": "2026-03-15T15:00"
    }


def test_a_private_value_is_never_unchanged():
    # Renders blank, so a blank with the clear checkbox must stay None.
    assert _restored({"secret": ""}, {"secret": "x"}) == {"secret": None}


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
