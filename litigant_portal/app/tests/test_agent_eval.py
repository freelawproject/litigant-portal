"""Tests for the agent eval harness under scripts/agent_eval.

All tests are DB-free and run in the fast suite. The Docker test image
ships without scripts/, so the module is skipped there.
"""

import json
from typing import Any

import pytest
from pydantic import ValidationError

pytest.importorskip("scripts.agent_eval.schema")

from scripts.agent_eval.judge import (  # noqa: E402
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


def _value_candidate(
    answer: str, expected_value: float | bool | None = 18.87
) -> dict[str, Any]:
    case = _case(
        expects_one_question=False,
        facts=[
            {
                "id": "filing-fee",
                "statement": "The fictional guide defines this value.",
                "critical": True,
                "value": expected_value,
            }
        ],
    )
    return {"case": case.model_dump(), "answer": answer}


def _value_response(
    status: str = "contradicted",
    value: float | bool | None = None,
    asserts_value: bool = False,
    evidence_ids: list[int] | None = None,
) -> dict[str, Any]:
    response = _grade().model_dump()
    response["facts"] = [
        {
            "fact_id": "filing-fee",
            "status": status,
            "value": value,
            "asserts_value": asserts_value,
            "evidence_ids": [1] if evidence_ids is None else evidence_ids,
            "explanation": "Assessment of the answer's claim.",
        }
    ]
    return response


@pytest.mark.parametrize(
    ("answer", "expected_value"),
    [
        (
            "There is no real Ohio Court of Common Peas and Poultry or "
            "Chicken Displacement Protection guide, so no official filing "
            "fee for a Habeas Cluckus petition exists.",
            18.87,
        ),
        (
            "There is no established filing fee; the Ohio Court of Common "
            "Peas and Poultry and its Chicken Displacement Protection guide "
            "are fictional.",
            42.0,
        ),
    ],
)
def test_v3_denial_without_an_amount_retains_critical_failure(
    answer: str, expected_value: float
) -> None:
    result = parse_response(
        json.dumps(_value_response()),
        _value_candidate(answer, expected_value),
        Weights(),
        version=3,
    )
    assert result["judge_format_version"] == 3
    assert result["grade"]["facts"][0]["asserts_value"] is False
    assert result["grade"]["facts"][0]["value"] is None
    assert result["score"]["overall"] == 0
    assert result["score"]["deal_breakers"][0]["category"] == "hard_fact"
    assert result["score"]["deal_breakers"][0]["evidence"] == answer


@pytest.mark.parametrize(
    ("status", "asserts_value", "value", "evidence_ids", "category"),
    [
        ("contradicted", True, None, [1], "missing_value"),
        ("contradicted", False, 42.0, [1], "unexpected_value"),
        ("supported", False, None, [1], "missing_value"),
        ("contradicted", False, None, [], "missing_evidence"),
        ("contradicted", False, None, [2], "evidence_ids"),
        ("contradicted", False, None, [1, 1], "evidence_ids"),
        ("omitted", True, 18.87, [], "unexpected_value"),
        ("uncertain", True, 18.87, [1], "unexpected_value"),
        ("uncertain", False, 18.87, [1], "unexpected_value"),
    ],
)
def test_v3_rejects_invalid_value_or_evidence(
    status: str,
    asserts_value: bool,
    value: float | bool | None,
    evidence_ids: list[int],
    category: str,
) -> None:
    response = _value_response(status, value, asserts_value, evidence_ids)
    with pytest.raises(InvalidGrade) as excinfo:
        parse_response(
            json.dumps(response),
            _value_candidate("The fee is $18.87."),
            Weights(),
            version=3,
        )
    assert excinfo.value.category == category


@pytest.mark.parametrize(
    ("status", "value", "asserts_value", "expected_value", "failed"),
    [
        ("supported", 18.87, True, 18.87, False),
        ("supported", 0.0, True, 0.0, False),
        ("supported", False, True, False, False),
        ("contradicted", 42.0, True, 18.87, True),
        ("contradicted", False, True, True, True),
        ("supported", 42.0, True, 18.87, True),
        ("supported", None, False, None, False),
        ("omitted", None, False, 18.87, False),
        ("uncertain", None, False, 18.87, False),
    ],
)
def test_v3_scores_value_assessments(
    status: str,
    value: float | bool | None,
    asserts_value: bool,
    expected_value: float | bool | None,
    failed: bool,
) -> None:
    result = parse_response(
        json.dumps(_value_response(status, value, asserts_value)),
        _value_candidate(
            "The answer supplies or defers the fact.", expected_value
        ),
        Weights(),
        version=3,
    )
    assert bool(result["score"]["deal_breakers"]) is failed


def test_v3_rejects_a_value_for_a_fact_without_an_answer_key_value() -> None:
    with pytest.raises(InvalidGrade) as excinfo:
        parse_response(
            json.dumps(_value_response("supported", 18.87, True)),
            _value_candidate("The fee is $18.87.", None),
            Weights(),
            version=3,
        )
    assert excinfo.value.category == "unexpected_value"


@pytest.mark.parametrize("flag", [None, "false", 0])
def test_v3_requires_a_boolean_value_assertion(flag: object) -> None:
    response = _value_response()
    response["facts"][0]["asserts_value"] = flag
    with pytest.raises(ValidationError, match="asserts_value"):
        parse_response(
            json.dumps(response),
            _value_candidate("No fee exists."),
            Weights(),
            version=3,
        )


def test_v3_does_not_default_a_missing_value_assertion() -> None:
    response = _value_response()
    response["facts"][0].pop("asserts_value")
    with pytest.raises(ValidationError, match="asserts_value"):
        parse_response(
            json.dumps(response),
            _value_candidate("No fee exists."),
            Weights(),
            version=3,
        )


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("value", [18.87, None])
def test_legacy_formats_keep_their_numeric_value_requirement(
    version: int, value: float | None
) -> None:
    answer = "The filing fee is $18.87."
    response = _value_response("supported", value, True)
    fact = response["facts"][0]
    fact.pop("asserts_value")
    if version == 1:
        fact.pop("evidence_ids")
        fact["evidence"] = answer
    candidate = _value_candidate(answer)
    if value is None:
        with pytest.raises(InvalidGrade) as excinfo:
            parse_response(json.dumps(response), candidate, Weights(), version)
        assert excinfo.value.category == "missing_value"
    else:
        result = parse_response(
            json.dumps(response), candidate, Weights(), version
        )
        assert result["judge_format_version"] == version
        assert "asserts_value" not in result["grade"]["facts"][0]
        assert result["score"]["overall"] == 75


@pytest.mark.parametrize("version", [1, 2])
def test_legacy_formats_reject_the_v3_value_assertion(version: int) -> None:
    response = _value_response()
    if version == 1:
        response["facts"][0].pop("evidence_ids")
        response["facts"][0]["evidence"] = "No fee exists."
    with pytest.raises(ValueError, match="asserts_value"):
        parse_response(
            json.dumps(response),
            _value_candidate("No fee exists."),
            Weights(),
            version,
        )
