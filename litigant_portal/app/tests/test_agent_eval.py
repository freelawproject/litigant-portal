"""Tests for the agent eval harness under scripts/agent_eval.

All tests are DB-free and run in the fast suite. The Docker test image
ships without scripts/, so the module is skipped there.
"""

import pytest

pytest.importorskip("scripts.agent_eval.schema")

from scripts.agent_eval.judge import (  # noqa: E402
    InvalidGrade,
    ends_with_question,
    validate_grade,
)
from scripts.agent_eval.schema import (  # noqa: E402
    DIMENSIONS,
    Case,
    Config,
    Grade,
    read_cases,
)


def _case(**overrides) -> Case:
    data = {
        "id": "shape-case",
        "group": "real",
        "court": "north-dakota",
        "topic": "adult-name-change",
        "question": "I need to change my name.",
        "references": ["standard.yml"],
        "facts": [
            {"id": "filing-location", "statement": "File in district court."}
        ],
        "acceptable_deferral": "Anything else may be deferred to the clerk.",
        "expects_one_question": True,
    }
    return Case.model_validate(data | overrides)


def _grade(deal_breakers=()) -> Grade:
    return Grade.model_validate(
        {
            "dimensions": {
                name: {"score": 3, "explanation": "fine"}
                for name in DIMENSIONS
            },
            "answer_outcome": "answered",
            "source_attribution": "supported",
            "facts": [
                {
                    "fact_id": "filing-location",
                    "status": "omitted",
                    "evidence": "",
                }
            ],
            "deal_breakers": list(deal_breakers),
        }
    )


MISSING_QUESTION = {
    "category": "reply_shape",
    "evidence": "",
    "explanation": "The reply asks no question.",
}
HEADING_ONLY = "**Do I need a hearing?**\n\nNot always. The judge decides if one is needed."


def test_every_case_in_cases_yml_loads():
    assert len(read_cases(Config())) > 20


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("File in your county. Which county do you live in?", True),
        ("File in your county.\n\n**Which county do you live in?**  \n", True),
        (HEADING_ONLY, False),
        ('You asked "do I need a hearing?" The answer is no.', False),
        ("File in your county.", False),
        ("", False),
    ],
    ids=[
        "plain-closing-question",
        "bold-closing-question-with-trailing-space",
        "question-mark-only-in-heading",
        "echoed-user-question",
        "no-question-mark",
        "empty",
    ],
)
def test_ends_with_question_looks_at_the_last_line(answer, expected):
    assert ends_with_question(answer) is expected


def test_harness_adds_reply_shape_when_question_mark_is_only_in_a_heading():
    failures = validate_grade(
        _grade(), _case(), HEADING_ONLY, evidence_verified=True
    )
    assert [f["category"] for f in failures] == ["reply_shape"]


def test_judge_missing_question_flag_is_accepted_when_heading_has_question_mark():
    failures = validate_grade(
        _grade([MISSING_QUESTION]),
        _case(),
        HEADING_ONLY,
        evidence_verified=True,
    )
    # The report counts categories per answer, so the judge's flag and the
    # harness fallback may both be present.
    assert {f["category"] for f in failures} == {"reply_shape"}


def test_judge_missing_question_flag_is_rejected_when_reply_ends_with_question():
    with pytest.raises(InvalidGrade) as excinfo:
        validate_grade(
            _grade([MISSING_QUESTION]),
            _case(),
            "File in your county. Which county do you live in?",
            evidence_verified=True,
        )
    assert excinfo.value.category == "missing_evidence"


def test_reply_shape_is_not_added_for_cases_without_the_flag():
    failures = validate_grade(
        _grade(),
        _case(expects_one_question=False),
        HEADING_ONLY,
        evidence_verified=True,
    )
    assert failures == []
