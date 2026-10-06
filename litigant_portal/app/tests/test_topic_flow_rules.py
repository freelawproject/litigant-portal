"""Rules evaluator tests (#970 POC): ``evaluate`` one gate, ``applying`` a corpus.

Pure functions over in-memory schema objects and a plain answers dict, so
the whole file is DB-free and runs in the fast suite.
"""

import pytest

from litigant_portal.app.topic_flow.rules import applying, evaluate
from litigant_portal.app.topic_flow.schema import (
    Condition,
    Corpus,
    FactGatherSection,
    InfoSection,
    Metadata,
    Question,
)

# --- evaluate ---------------------------------------------------------------


def _leaf(**operator):
    return Condition.model_validate({"fact": "poc_path", **operator})


@pytest.mark.parametrize(
    ("condition", "answers", "expected"),
    [
        (_leaf(equals="renter"), {"poc_path": "renter"}, True),
        (_leaf(equals="renter"), {"poc_path": "marina"}, False),
        (_leaf(equals="renter"), {}, False),
        (_leaf(not_equals="marina"), {"poc_path": "renter"}, True),
        (_leaf(not_equals="marina"), {"poc_path": "marina"}, False),
        (_leaf(not_equals="marina"), {}, False),
        (_leaf(**{"in": ["renter", "marina"]}), {"poc_path": "marina"}, True),
        (
            _leaf(**{"in": ["renter", "marina"]}),
            {"poc_path": "neighbor"},
            False,
        ),
        (_leaf(**{"in": ["renter", "marina"]}), {}, False),
        (_leaf(answered=True), {"poc_path": "renter"}, True),
        (_leaf(answered=True), {}, False),
        (_leaf(answered=False), {}, True),
        (_leaf(answered=False), {"poc_path": "renter"}, False),
    ],
    ids=[
        "equals-match",
        "equals-mismatch",
        "equals-missing-is-false",
        "not-equals-match",
        "not-equals-mismatch",
        "not-equals-missing-is-false",
        "in-match",
        "in-mismatch",
        "in-missing-is-false",
        "answered-present",
        "answered-missing",
        "not-answered-missing-is-true",
        "not-answered-present",
    ],
)
def test_a_leaf_evaluates_against_present_and_missing_facts(
    condition, answers, expected
):
    assert evaluate(condition, answers) is expected


@pytest.mark.parametrize(
    "value",
    ["", None],
    ids=["blank-string", "cleared-none"],
)
def test_a_blank_or_cleared_answer_counts_as_missing(value):
    # A cleared answer stores None and a blank field submits "": neither is a
    # fact anyone answered, so neither opens a gate.
    assert evaluate(_leaf(equals="renter"), {"poc_path": value}) is False
    assert evaluate(_leaf(answered=False), {"poc_path": value}) is True


def test_no_condition_always_holds():
    assert evaluate(None, {}) is True


RENTER = {"fact": "poc_path", "equals": "renter"}
NOTICE = {"fact": "poc_received_notice", "equals": "yes"}


@pytest.mark.parametrize(
    ("condition", "answers", "expected"),
    [
        (
            {"all": [RENTER, NOTICE]},
            {"poc_path": "renter", "poc_received_notice": "yes"},
            True,
        ),
        ({"all": [RENTER, NOTICE]}, {"poc_path": "renter"}, False),
        ({"any": [RENTER, NOTICE]}, {"poc_received_notice": "yes"}, True),
        ({"any": [RENTER, NOTICE]}, {}, False),
        ({"not": RENTER}, {"poc_path": "marina"}, True),
        ({"not": RENTER}, {"poc_path": "renter"}, False),
        ({"not": RENTER}, {}, True),
        (
            {
                "all": [
                    RENTER,
                    {
                        "any": [
                            NOTICE,
                            {
                                "not": {
                                    "fact": "poc_notice_date",
                                    "answered": True,
                                }
                            },
                        ]
                    },
                ]
            },
            {"poc_path": "renter", "poc_received_notice": "no"},
            True,
        ),
        (
            {
                "all": [
                    RENTER,
                    {
                        "any": [
                            NOTICE,
                            {
                                "not": {
                                    "fact": "poc_notice_date",
                                    "answered": True,
                                }
                            },
                        ]
                    },
                ]
            },
            {
                "poc_path": "renter",
                "poc_received_notice": "no",
                "poc_notice_date": "2026-01-01",
            },
            False,
        ),
    ],
    ids=[
        "all-both-hold",
        "all-one-missing",
        "any-one-holds",
        "any-none-hold",
        "not-of-false",
        "not-of-true",
        "not-of-missing-is-true",
        "nested-holds",
        "nested-fails",
    ],
)
def test_combinators_compose(condition, answers, expected):
    assert evaluate(Condition.model_validate(condition), answers) is expected


# --- applying ---------------------------------------------------------------
# The POC corpus shape: a three-way path, a renter-only section with a
# two-way branch and a date gated on it, per-path info sections, and a
# two-fact section.


def _info(id, when=None):
    return InfoSection(kind="info", id=id, heading="H", body="B", when=when)


def _corpus():
    return Corpus(
        metadata=Metadata(court="c", topic="t", role="r", title="T"),
        sections=[
            _info("welcome"),
            FactGatherSection(
                kind="fact_gather",
                id="who_are_you",
                questions=[
                    Question(
                        id="poc_path",
                        label="Role",
                        type="choice",
                        choices=["renter", "marina", "neighbor"],
                    )
                ],
            ),
            FactGatherSection(
                kind="fact_gather",
                id="renter_notice",
                when=RENTER,
                questions=[
                    Question(
                        id="poc_received_notice",
                        label="Notice?",
                        type="choice",
                        choices=["yes", "no"],
                    ),
                    Question(
                        id="poc_notice_date",
                        label="Date",
                        type="date",
                        when=NOTICE,
                    ),
                ],
            ),
            _info("renter_steps", when=RENTER),
            _info(
                "marina_steps", when={"fact": "poc_path", "equals": "marina"}
            ),
            _info("answer_urgent", when={"all": [RENTER, NOTICE]}),
            _info("recap"),
        ],
    )


def _ids(frozen):
    return sorted(frozen)


def test_sections_without_a_when_always_apply():
    result = applying(_corpus(), {})
    assert result.section_ids >= {"welcome", "who_are_you", "recap"}


def test_nothing_gated_applies_before_the_path_is_answered():
    result = applying(_corpus(), {})
    assert _ids(result.section_ids) == ["recap", "welcome", "who_are_you"]
    assert _ids(result.question_ids) == ["poc_path"]


def test_the_path_opens_its_own_sections_only():
    result = applying(_corpus(), {"poc_path": "renter"})
    assert "renter_notice" in result.section_ids
    assert "renter_steps" in result.section_ids
    assert "marina_steps" not in result.section_ids
    assert "answer_urgent" not in result.section_ids


def test_a_question_gate_within_an_applying_section_is_honoured():
    without = applying(_corpus(), {"poc_path": "renter"})
    with_notice = applying(
        _corpus(), {"poc_path": "renter", "poc_received_notice": "yes"}
    )
    assert "poc_notice_date" not in without.question_ids
    assert "poc_notice_date" in with_notice.question_ids


def test_a_two_fact_gate_needs_both_facts():
    answers = {"poc_path": "renter", "poc_received_notice": "yes"}
    assert "answer_urgent" in applying(_corpus(), answers).section_ids
    answers["poc_received_notice"] = "no"
    assert "answer_urgent" not in applying(_corpus(), answers).section_ids


def test_a_question_in_a_hidden_section_is_not_asked_even_if_its_gate_holds():
    # poc_notice_date's own gate (notice = yes) is satisfied by the stored
    # answer, but its section is gated on renter and the path is marina.
    result = applying(
        _corpus(), {"poc_path": "marina", "poc_received_notice": "yes"}
    )
    assert "poc_received_notice" not in result.question_ids
    assert "poc_notice_date" not in result.question_ids


def test_applying_answers_keeps_only_asked_questions():
    result = applying(
        _corpus(),
        {
            "poc_path": "marina",
            "poc_received_notice": "yes",
            "poc_notice_date": "2026-01-01",
        },
    )
    assert result.applying_answers == {"poc_path": "marina"}


def test_a_gate_reading_a_hidden_fact_treats_it_as_missing():
    # The path-switch scenario: the renter's stored facts stop applying when
    # the path is marina, so the two-fact rule is false although
    # poc_received_notice = yes is still in the store.
    stored = {
        "poc_path": "renter",
        "poc_received_notice": "yes",
        "poc_notice_date": "2026-01-01",
    }
    as_renter = applying(_corpus(), stored)
    assert "answer_urgent" in as_renter.section_ids
    assert as_renter.applying_answers == stored

    as_marina = applying(_corpus(), {**stored, "poc_path": "marina"})
    assert "answer_urgent" not in as_marina.section_ids
    assert "poc_received_notice" not in as_marina.applying_answers

    back = applying(_corpus(), stored)
    assert back.applying_answers == stored


def test_an_unanswered_asked_question_is_absent_from_applying_answers():
    result = applying(_corpus(), {"poc_path": "renter"})
    assert "poc_received_notice" in result.question_ids
    assert "poc_received_notice" not in result.applying_answers


def test_applying_offers_section_and_question_predicates():
    corpus = _corpus()
    result = applying(corpus, {"poc_path": "renter"})
    renter_notice = corpus.sections[2]
    assert result.section(renter_notice) is True
    assert result.question(renter_notice.questions[0]) is True
    assert result.question(renter_notice.questions[1]) is False
