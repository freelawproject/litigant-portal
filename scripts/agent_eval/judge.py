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
from .schema import (
    FACT_DIMENSIONS,
    HERE,
    QUALITY_DIMENSIONS,
    Case,
    CitedGrade,
    Grade,
    Weights,
)

FORMAT_VERSION = 2


class InvalidGrade(ValueError):
    """
    A saved, recoverable judgment failure with a concise reporting category.
    """

    def __init__(self, category: str, message: str):
        self.category = category
        super().__init__(message)


def _excerpt_position(answer: str, excerpt: str, start: int) -> int:
    """
    Match complete words and amounts, not 160 inside 1600 or -160.
    """
    while (position := answer.find(excerpt, start)) >= 0:
        end = position + len(excerpt)
        before, after = (
            answer[max(0, position - 1) : position],
            answer[end : end + 1],
        )
        left = excerpt[0].isalnum() and (before.isalnum() or before == "_")
        right = excerpt[-1].isalnum() and (after.isalnum() or after == "_")
        if excerpt[0].isdigit():
            left |= before in {"-", "+", "−"} or (
                before in {".", ","}
                and position > 1
                and answer[position - 2].isdigit()
            )
        if excerpt[-1].isdigit():
            right |= (
                after in {".", ","} and answer[end + 1 : end + 2].isdigit()
            )
        if not left and not right:
            return position
        start = position + 1
    return -1


def _legacy_match(answer: str, evidence: str) -> bool:
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
        position = _excerpt_position(answer, piece, cursor)
        if position < 0:
            return False
        cursor = position + len(piece)
    return not evidence or cursor > 0


def contains_evidence(answer: str, evidence: str) -> bool:
    """
    Recover legacy quotations without accepting paraphrases or changed words.

    Separate quotations need not follow document order. Ellipsis-separated
    fragments within a quotation must still occur in their original order.
    """
    if _legacy_match(answer, evidence):
        return True

    def rendered(text):
        text = unicodedata.normalize("NFKC", text).translate(
            str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})
        )
        text = re.sub(r"(\*\*|__|`)(.+?)\1", r"\2", text, flags=re.S)
        text = re.sub(r"\[([^\]]+)\]\([^\s)]+\)", r"\1", text)
        text = re.sub(
            r"(?m)^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|>\s*)", "", text
        )
        return " ".join(text.replace("|", " ").split()).casefold()

    answer, evidence = rendered(answer), rendered(evidence)
    quotes = re.findall(r'"([^\"]+)"', evidence)
    found = False
    for piece in quotes or [evidence]:
        cursor = 0
        for segment in re.split(r"\.\.\.|…", piece):
            segment = segment.strip().strip('"').strip()
            segment = segment.rstrip(".,;:!?").rstrip()
            if not segment:
                continue
            position = _excerpt_position(answer, segment, cursor)
            if position < 0:
                return False
            cursor = position + len(segment)
            found = True
    return not evidence or found


def validate_grade(
    grade: Grade, case: Case, answer: str, *, evidence_verified=False
) -> list[dict]:
    ids = [assessment.fact_id for assessment in grade.facts]
    if len(ids) != len(set(ids)) or set(ids) != {
        fact.id for fact in case.facts
    }:
        raise InvalidGrade(
            "fact_coverage",
            "Judge must assess each expected fact exactly once.",
        )
    failures = [item.model_dump() for item in grade.deal_breakers]
    for failure in failures:
        if failure["category"] == "missed_escalation":
            if not case.requires_escalation:
                raise InvalidGrade(
                    "escalation", "Judge invented an escalation requirement."
                )
        elif not failure["evidence"]:
            raise InvalidGrade(
                "missing_evidence", "A deal breaker needs answer evidence."
            )
        if not evidence_verified and not contains_evidence(
            answer, failure["evidence"]
        ):
            raise InvalidGrade(
                "deal_breaker_evidence",
                "Deal-breaker evidence is not in the answer.",
            )
    facts = {fact.id: fact for fact in case.facts}
    for assessment in grade.facts:
        fact = facts[assessment.fact_id]
        asserted = assessment.status in {"supported", "contradicted"}
        if asserted and not assessment.evidence:
            raise InvalidGrade(
                "missing_evidence",
                f"Fact {fact.id}: asserted facts need evidence.",
            )
        if not evidence_verified and not contains_evidence(
            answer, assessment.evidence
        ):
            raise InvalidGrade(
                "fact_evidence",
                f"Fact {fact.id}: evidence is not in the answer.",
            )
        mismatch = False
        if asserted and fact.value is not None:
            if assessment.value is None:
                raise InvalidGrade(
                    "missing_value",
                    f"Fact {fact.id}: extract the asserted value; "
                    "use omitted/uncertain when no value is asserted.",
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


def answer_passages(answer: str) -> list[dict]:
    return [
        {"id": i, "text": line}
        for i, line in enumerate(
            (line for line in answer.splitlines() if line.strip()), 1
        )
    ]


def contract(run: Path) -> dict:
    """
    Freeze the original scoring rubric with the current response protocol.
    """
    return {
        "format_version": FORMAT_VERSION,
        "instructions": (run / "references" / "rubric.md").read_text()
        + "\n\n"
        + (HERE / "judge-format.md").read_text(),
        "schema": CitedGrade.model_json_schema(),
    }


def parse_response(
    text: str, candidate: dict, weights: Weights, version=1
) -> dict:
    """
    Validate and score a response without contacting a model or writing files.
    """
    if version == 1:
        grade = Grade.model_validate_json(text)
    elif version == FORMAT_VERSION:
        cited = CitedGrade.model_validate_json(text)
        passages = {
            row["id"]: row["text"]
            for row in answer_passages(candidate["answer"])
        }
        content = cited.model_dump()
        for fact in content["facts"]:
            if (
                fact["status"] in {"omitted", "uncertain"}
                and fact["value"] is not None
            ):
                raise InvalidGrade(
                    "unexpected_value",
                    f"Fact {fact['fact_id']}: omitted/uncertain values must be null.",
                )
        for item in [*content["facts"], *content["deal_breakers"]]:
            ids = item.pop("evidence_ids")
            if len(ids) != len(set(ids)) or any(
                i not in passages for i in ids
            ):
                raise InvalidGrade(
                    "evidence_ids",
                    f"Invalid or duplicate answer passage IDs: {ids}",
                )
            item["evidence"] = "\n".join(passages[i] for i in ids)
        grade = Grade.model_validate(content)
    else:
        raise ValueError(f"Unsupported judge format version: {version}")
    failures = validate_grade(
        grade,
        Case.model_validate(candidate["case"]),
        candidate["answer"],
        evidence_verified=version == FORMAT_VERSION,
    )
    return {
        "grade": grade.model_dump(),
        "score": score(grade, failures, weights),
        "judge_format_version": version,
    }


def judgment_path(run: Path, folder: Path, name: str) -> Path:
    path = (folder / name).resolve()
    if not path.is_relative_to((run / "judgments").resolve()):
        raise ValueError("Judgment reference escapes this run's judgments.")
    return path


def paid_calls(run: Path, path: Path) -> tuple[Path, list[dict]]:
    """
    Resolve recovered results to their original paid call records.
    """
    seen = set()
    while path not in seen:
        seen.add(path)
        row = json.loads(path.read_text())
        if "calls_source" not in row:
            return path, row["calls"]
        path = judgment_path(run, run, row["calls_source"])
    raise ValueError("Cycle in recovered judgment cost references.")


async def evaluate(
    record: dict, config, run: Path, protocol: dict, capture=lambda text: None
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
        "answer_passages": answer_passages(record["answer"]),
        "fictional": case.group == "fictional",
        "references": references,
        "expected_facts": [fact.model_dump() for fact in case.facts],
        "acceptable_deferral": case.acceptable_deferral,
        "requires_escalation": case.requires_escalation,
    }
    if protocol["format_version"] != FORMAT_VERSION:
        raise ValueError("Unsupported live judge format.")
    instructions = protocol["instructions"]
    instructions += "\nReturn only JSON matching this schema:\n" + json.dumps(
        protocol["schema"]
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
    return parse_response(text, record, config.weights, FORMAT_VERSION)
