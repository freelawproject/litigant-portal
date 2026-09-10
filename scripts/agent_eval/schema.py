"""
Versioned benchmark inputs and judge contracts.
"""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FACT_DIMENSIONS = ("correctness", "completeness", "grounding", "uncertainty")
QUALITY_DIMENSIONS = ("clarity", "actionability", "relevance")
DIMENSIONS = FACT_DIMENSIONS + QUALITY_DIMENSIONS
SLUG = r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$"
type Slug = Annotated[str, Field(pattern=SLUG)]
type System = Literal["raw", "old", "new"]


class Schema(BaseModel):
    """
    Reject misspelled options and nonfinite scoring values.
    """

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Weights(Schema):
    facts: float = Field(default=0.7, ge=0, le=1)
    qualitative: float = Field(default=0.3, ge=0, le=1)

    @model_validator(mode="after")
    def total(self) -> Self:
        if abs(self.facts + self.qualitative - 1) > 1e-9:
            raise ValueError("Weights must sum to one.")
        return self


class Price(Schema):
    input_per_million: float = Field(ge=0)
    output_per_million: float = Field(ge=0)
    cached_input_per_million: float | None = Field(default=None, ge=0)
    source: str = Field(min_length=1)


class Config(Schema):
    slug: Slug = "initial-baseline"
    systems: list[System] = Field(default=["raw", "old", "new"], min_length=1)
    models: list[Slug] = Field(default=["luna", "terra"], min_length=1)
    model_ids: dict[Slug, str] = Field(
        default_factory=lambda: {
            name: f"bedrock_mantle/openai.gpt-5.6-{name}"
            for name in ("luna", "terra", "sol")
        }
    )
    repetitions: int = Field(default=3, ge=1, strict=True)
    judge_model: Slug = "sol"
    legacy_fast_model: Slug | None = "luna"
    weights: Weights = Field(default_factory=Weights)
    cases: list[Slug] | None = None
    timeout_seconds: float = Field(default=300, gt=0)
    seed: int = 179
    prices: dict[str, Price] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_and_resolved(self) -> Self:
        for values in (self.systems, self.models, self.cases or []):
            if len(values) != len(set(values)):
                raise ValueError("Selections must not contain duplicates.")
        aliases = self.models + [self.judge_model]
        if self.legacy_fast_model is not None:
            aliases.append(self.legacy_fast_model)
        if not set(aliases) <= self.model_ids.keys():
            raise ValueError("Every selected model needs a model_ids entry.")
        if any(not value.strip() for value in self.model_ids.values()):
            raise ValueError("Model identifiers must not be empty.")
        return self


class Fact(Schema):
    id: Slug
    statement: str
    critical: bool = False
    value: float | bool | None = None


class Case(Schema):
    id: Slug
    group: Literal["real", "fictional"]
    fixture: Literal["current", "chickens-a", "chickens-b"] = "current"
    court: Slug
    topic: Slug
    question: str = Field(min_length=1)
    references: list[str] = Field(min_length=1)
    facts: list[Fact] = Field(min_length=1)
    acceptable_deferral: str
    requires_escalation: bool = False
    review_status: str = (
        "draft; checked against repository corpus, not court reviewed"
    )

    @model_validator(mode="after")
    def unique_facts(self) -> Self:
        ids = [fact.id for fact in self.facts]
        if len(ids) != len(set(ids)):
            raise ValueError("Fact IDs must be unique within a case.")
        return self


class Dimension(Schema):
    score: int = Field(ge=0, le=4, strict=True)
    explanation: str = Field(min_length=1)


class Assessment(Schema):
    fact_id: str
    status: Literal["supported", "contradicted", "omitted", "uncertain"]
    evidence: str
    value: float | bool | None = None


class DealBreaker(Schema):
    category: Literal[
        "citation",
        "hard_fact",
        "legal_direction",
        "missed_escalation",
        "unsupported_claim",
    ]
    evidence: str
    explanation: str = Field(min_length=1)


class Grade(Schema):
    dimensions: dict[str, Dimension]
    facts: list[Assessment]
    deal_breakers: list[DealBreaker]
    answer_outcome: Literal["answered", "partial", "deferred"]
    source_attribution: Literal["supported", "absent", "unsupported"]

    @model_validator(mode="after")
    def all_dimensions(self) -> Self:
        if set(self.dimensions) != set(DIMENSIONS):
            raise ValueError("Judge must score all seven dimensions.")
        return self


def fingerprint(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def read_config(path: Path) -> Config:
    return Config.model_validate(yaml.safe_load(path.read_text()))


def read_cases(config: Config) -> list[Case]:
    cases = [
        Case.model_validate(row)
        for row in yaml.safe_load((HERE / "cases.yml").read_text())
    ]
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Case IDs must be unique.")
    if config.cases is not None:
        if not config.cases or not set(config.cases) <= set(ids):
            raise ValueError("Select at least one known case ID.")
        cases = [case for case in cases if case.id in config.cases]
    return cases


def write_json(path: Path, value) -> None:
    """
    Replace each artifact atomically so interruptions leave readable JSON.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_suffix(".tmp")
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    pending.replace(path)


def verify_references(run: Path, manifest: dict) -> None:
    """
    Refuse to grade or compare a silently edited saved benchmark definition.
    """
    for name, expected in manifest["reference_hashes"].items():
        if fingerprint((run / "references" / name).read_text()) != expected:
            raise ValueError(f"Saved reference changed: {name}")
    expected = fingerprint(
        {
            "cases": manifest["cases"],
            "references": manifest["reference_hashes"],
            "scoring_version": manifest["scoring_version"],
        }
    )
    if expected != manifest["benchmark_id"]:
        raise ValueError("Saved benchmark definition changed.")
