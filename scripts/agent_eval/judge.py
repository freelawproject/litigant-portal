"""
Grade saved answers, then apply deterministic checks and versioned weights.
"""

import json
import math
import os
import re
import unicodedata
from pathlib import Path
from statistics import mean

from .provider import data
from .schema import FACT_DIMENSIONS, QUALITY_DIMENSIONS, Case, Grade, Weights


def contains_evidence(answer: str, evidence: str) -> bool:
    """
    Match rendered excerpts in order, permitting quotes and explicit ellipses.

    Formatting and whitespace may differ; words and their order may not.
    """

    def rendered(text):
        text = unicodedata.normalize("NFKC", text)
        text = text.translate(
            str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
        )
        text = re.sub(r"(\*\*|__|`)(.+?)\1", r"\2", text, flags=re.S)
        text = re.sub(r"\[([^\]]+)\]\([^\s)]+\)", r"\1", text)
        return " ".join(text.split())

    answer, evidence = rendered(answer), rendered(evidence)
    quotes = re.findall(r'"([^\"]+)"', evidence)
    # A judge can place connecting commentary between explicitly quoted
    # excerpts. Verify every quoted span, never the commentary as a quote.
    pieces = (
        quotes
        if evidence.startswith('"') and len(quotes) > 1
        else re.split(r'\.\.\.|…|"\s+and\s+"', evidence)
    )
    pieces = [
        part for piece in pieces for part in re.split(r"\.\.\.|…", piece)
    ]
    cursor = 0
    for piece in pieces:
        piece = piece.strip().strip('"').strip()
        if not piece:
            continue
        position = answer.find(piece, cursor)
        if position < 0:
            return False
        cursor = position + len(piece)
    return not evidence or cursor > 0


def validate_grade(grade: Grade, case: Case, answer: str) -> list[dict]:
    ids = [assessment.fact_id for assessment in grade.facts]
    if len(ids) != len(set(ids)) or set(ids) != {
        fact.id for fact in case.facts
    }:
        raise ValueError("Judge must assess each expected fact exactly once.")
    failures = [item.model_dump() for item in grade.deal_breakers]
    for failure in failures:
        if failure["category"] == "missed_escalation":
            if not case.requires_escalation:
                raise ValueError("Judge invented an escalation requirement.")
        elif not failure["evidence"]:
            raise ValueError("A deal breaker needs answer evidence.")
        if not contains_evidence(answer, failure["evidence"]):
            raise ValueError("Deal-breaker evidence is not in the answer.")
    facts = {fact.id: fact for fact in case.facts}
    for assessment in grade.facts:
        fact = facts[assessment.fact_id]
        asserted = assessment.status in {"supported", "contradicted"}
        if asserted and not assessment.evidence:
            raise ValueError("Asserted facts need answer evidence.")
        if not contains_evidence(answer, assessment.evidence):
            raise ValueError("Fact evidence is not in the answer.")
        mismatch = False
        if asserted and fact.value is not None:
            if assessment.value is None:
                raise ValueError(
                    "Judge must extract an asserted fact's value."
                )
            if isinstance(fact.value, bool):
                mismatch = (
                    type(assessment.value) is not bool
                    or assessment.value != fact.value
                )
            else:
                mismatch = isinstance(
                    assessment.value, bool
                ) or not math.isclose(
                    assessment.value, fact.value, rel_tol=0, abs_tol=1e-6
                )
        if fact.critical and (assessment.status == "contradicted" or mismatch):
            failures.append(
                {
                    "category": "hard_fact",
                    "evidence": assessment.evidence,
                    "explanation": f"Failed expected fact: {fact.id}",
                    "check": "reference fact/value check",
                }
            )
    return failures


def score(grade: Grade, failures: list[dict], weights: Weights) -> dict:
    dimensions = {
        name: row.score * 25 for name, row in grade.dimensions.items()
    }
    facts = mean(dimensions[name] for name in FACT_DIMENSIONS)
    qualitative = mean(dimensions[name] for name in QUALITY_DIMENSIONS)
    uncapped = facts * weights.facts + qualitative * weights.qualitative
    return {
        "overall": 0 if failures else uncapped,
        "uncapped": uncapped,
        "facts": facts,
        "qualitative": qualitative,
        "dimensions": dimensions,
        "deal_breakers": failures,
        "answer_outcome": grade.answer_outcome,
        "source_attribution": grade.source_attribution,
    }


async def evaluate(
    record: dict, config, run: Path, capture=lambda text: None
) -> dict:
    import litellm
    from litellm.llms.custom_httpx.http_handler import AsyncHTTPHandler

    case = Case.model_validate(record["case"])
    references = {
        path: (run / "references" / path).read_text()
        for path in case.references
    }
    payload = {
        "question": case.question,
        "answer": record["answer"],
        "fictional": case.group == "fictional",
        "references": references,
        "expected_facts": [fact.model_dump() for fact in case.facts],
        "acceptable_deferral": case.acceptable_deferral,
        "requires_escalation": case.requires_escalation,
    }
    instructions = (run / "references" / "rubric.md").read_text()
    instructions += (
        "\nReturn only JSON matching this schema:\n"
        + (run / "references" / "judge-schema.json").read_text()
    )
    client = AsyncHTTPHandler()
    try:
        response = await litellm.aresponses(
            model=config.model_ids[config.judge_model],
            api_key=os.environ["AWS_BEARER_TOKEN_BEDROCK"],
            client=client,
            instructions=instructions,
            input=json.dumps(payload),
            stream=False,
            store=False,
            num_retries=0,
            caching=False,
        )
    finally:
        await client.close()
    result = data(response)
    if result.get("status") != "completed":
        raise ValueError("Judge did not complete its response.")
    text = "".join(
        part.get("text", "")
        for item in result.get("output", [])
        if item.get("type") == "message"
        for part in item.get("content", [])
        if part.get("type") == "output_text"
    )
    capture(text)
    grade = Grade.model_validate_json(text)
    failures = validate_grade(grade, case, record["answer"])
    return {
        "grade": grade.model_dump(),
        "score": score(grade, failures, config.weights),
    }
