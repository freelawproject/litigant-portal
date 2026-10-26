"""Tests for the agent eval harness under scripts/agent_eval.

All tests are DB-free and run in the fast suite. The Docker test image
ships without scripts/, so the module is skipped there.
"""

import json

import pytest

pytest.importorskip("scripts.agent_eval.schema")

from scripts.agent_eval.judge import (  # noqa: E402
    FORMAT_VERSION,
    InvalidGrade,
    ends_with_question,
    parse_response,
    validate_grade,
)
from scripts.agent_eval.schema import (  # noqa: E402
    DIMENSIONS,
    Case,
    Config,
    Grade,
    Weights,
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


def test_system_tags() -> None:
    expected = ["raw", "current", "standalone"]
    assert Config().systems == expected
    for tags in (expected, ["raw", "old", "new"]):
        assert Config.model_validate({"systems": tags}).systems == expected


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("File in your county. Which county do you live in?", True),
        ("File in your county.\n\n**Which county do you live in?**  \n", True),
        ("Six months there is required. Which county? [source:nd/x]", True),
        ("Which county?\n[source:nd/x]", True),
        (
            "Which county?\n\n[source:nd/x] [source:nd/y]\n[source:nd/z]\n",
            True,
        ),
        ("[source:nd/x]", False),
        ("**Which county? [source:nd/x]**", True),
        ("Which county?\n**[source:nd/x]**", True),
        ("Which county? [source:nd/x])", True),
        ("Which county? [source:nd/x].", True),
        ('Which county?"', True),
        ("Which county?)", True),
        (HEADING_ONLY, False),
        (HEADING_ONLY + " [source:nd/x]", False),
        ('You asked "do I need a hearing?" The answer is no.', False),
        ("File in your county.", False),
        ("", False),
    ],
    ids=[
        "plain-closing-question",
        "bold-closing-question-with-trailing-space",
        "closing-question-then-citation",
        "closing-question-then-citation-line",
        "closing-question-then-citation-lines",
        "citation-only",
        "bold-around-question-and-citation",
        "bold-citation-line",
        "citation-then-closing-parenthesis",
        "citation-then-period",
        "closing-question-in-quotes",
        "closing-question-in-parentheses",
        "question-mark-only-in-heading",
        "question-mark-only-in-heading-with-citation",
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


@pytest.fixture
def value_judgment() -> tuple[dict, dict]:
    case = _case(
        expects_one_question=False,
        facts=[
            {
                "id": "filing-fee",
                "statement": "The filing fee is $18.87.",
                "critical": True,
                "value": 18.87,
            }
        ],
    )
    response = _grade().model_dump()
    response["facts"] = [
        {
            "fact_id": "filing-fee",
            "status": "contradicted",
            "value": None,
            "evidence_ids": [1],
            "explanation": "The answer denies that the fee exists.",
        }
    ]
    return {"case": case.model_dump(), "answer": "No fee exists."}, response


@pytest.mark.parametrize(
    "version", [1, 2, 3, None], ids=["v1", "v2", "v3", "current"]
)
def test_denial_without_value_keeps_critical_failure(
    value_judgment: tuple[dict, dict], version: int | None
) -> None:
    candidate, response = value_judgment
    fact = response["facts"][0]
    if version == 1:
        fact["evidence"] = candidate["answer"]
        fact.pop("evidence_ids")
    elif version == 3:
        fact["asserts_value"] = False
    version = FORMAT_VERSION if version is None else version
    if version < 3:
        with pytest.raises(InvalidGrade) as excinfo:
            parse_response(json.dumps(response), candidate, Weights(), version)
        assert excinfo.value.category == "missing_value"
    else:
        result = parse_response(
            json.dumps(response), candidate, Weights(), version
        )
        assert result["score"]["overall"] == 0
        assert result["score"]["deal_breakers"][0]["category"] == "hard_fact"
        assert result["grade"]["facts"][0]["evidence"] == candidate["answer"]


def test_supported_fact_still_requires_value(
    value_judgment: tuple[dict, dict],
) -> None:
    candidate, response = value_judgment
    response["facts"][0]["status"] = "supported"
    with pytest.raises(InvalidGrade) as excinfo:
        parse_response(
            json.dumps(response), candidate, Weights(), FORMAT_VERSION
        )
    assert excinfo.value.category == "missing_value"


@pytest.mark.parametrize(
    ("value", "answer"),
    [(0.0, "Filing is free."), (False, "You are not eligible.")],
)
def test_zero_and_false_are_values(
    value_judgment: tuple[dict, dict], value: float | bool, answer: str
) -> None:
    candidate, response = value_judgment
    candidate["answer"] = answer
    candidate["case"]["facts"][0]["value"] = value
    response["facts"][0].update(status="supported", value=value)
    result = parse_response(
        json.dumps(response), candidate, Weights(), FORMAT_VERSION
    )
    assert result["grade"]["facts"][0]["value"] == value
    assert result["score"]["overall"] == 75
    assert result["score"]["deal_breakers"] == []
