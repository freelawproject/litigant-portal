"""
Versioned benchmark inputs and judge contracts.
"""

import hashlib
import json
from pathlib import Path
from typing import Annotated, Literal, Self, get_args

import yaml
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

from litigant_portal.agents.bedrock import model_tiers

from .models import pinned_evaluator_options

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
FACT_DIMENSIONS = ("correctness", "completeness", "grounding", "uncertainty")
QUALITY_DIMENSIONS = ("clarity", "actionability", "relevance")
DIMENSIONS = FACT_DIMENSIONS + QUALITY_DIMENSIONS
SLUG = r"^[a-z0-9]+(?:[-_][a-z0-9]+)*$"
type Slug = Annotated[str, Field(pattern=SLUG)]
type System = Literal["raw", "no_judge", "current"]
type FactStatus = Literal["supported", "contradicted", "omitted", "uncertain"]
type FailureCategory = Literal[
    "citation",
    "hard_fact",
    "legal_direction",
    "missed_escalation",
    "reply_shape",
    "unsupported_claim",
]
FAILURE_CATEGORIES = get_args(FailureCategory.__value__)
type PassageID = Annotated[int, Field(gt=0, strict=True)]


def normalize_system(system: str) -> str:
    """
    Normalize the legacy chat tag and reject unsupported evaluation systems.
    """
    if system == "old":
        return "current"
    if system not in get_args(System.__value__):
        raise ValueError(
            f"Unsupported evaluation system: {system}. "
            "Use raw, no_judge, or current."
        )
    return system


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


def saved_evaluator_model(config: dict) -> str | None:
    return config.get("evaluator_model") or config.get("model_ids", {}).get(
        config.get("judge_model")
    )


class GradingConfig(Schema):
    evaluator_model: str = "bedrock_mantle/us-east-1/openai.gpt-6.1-sol"
    weights: Weights = Field(default_factory=Weights)
    timeout_seconds: float = Field(default=300, gt=0)
    prices: dict[str, Price] = Field(default_factory=dict)

    @classmethod
    def from_saved(cls, config: dict) -> Self:
        """
        Read historical grading settings without changing their model choice.
        """
        return cls.model_validate(
            {
                **{
                    key: config[key]
                    for key in cls.model_fields
                    if key in config
                },
                "evaluator_model": saved_evaluator_model(config),
            }
        )


class Config(GradingConfig):
    slug: Slug = "initial-baseline"
    systems: list[Annotated[System, BeforeValidator(normalize_system)]] = (
        Field(default=["raw", "no_judge", "current"], min_length=1)
    )
    models: list[str] = Field(
        default=["auto/openai.luna", "auto/openai.terra"], min_length=1
    )
    judges: list[str] = Field(default=["auto/openai.luna"])
    repetitions: int = Field(default=3, ge=1, strict=True)
    legacy_fast_model: str | None = "auto/openai.luna"
    cases: list[Slug] | None = None
    seed: int = 179

    @model_validator(mode="after")
    def unique_and_resolved(self) -> Self:
        for values in (
            self.systems,
            self.models,
            self.judges,
            self.cases or [],
        ):
            if len(values) != len(set(values)):
                raise ValueError("Selections must not contain duplicates.")
        aliases = self.models + self.judges
        if "current" in self.systems and not self.judges:
            raise ValueError("The current system requires at least one judge.")
        if self.legacy_fast_model is not None:
            aliases.append(self.legacy_fast_model)
        if not set(aliases) <= model_tiers().keys():
            raise ValueError("Select enabled auto/ model identifiers.")
        pinned_evaluator_options(self.evaluator_model)
        return self


def configurations(config: dict) -> list[tuple[str, str, str | None]]:
    """
    Cross judges only with current; historical runs have no judge axis.
    """
    return [
        (normalize_system(system), model, judge)
        for system in config["systems"]
        for model in config["models"]
        for judge in (
            config.get("judges", [None])
            if normalize_system(system) == "current"
            else [None]
        )
    ]


class Fact(Schema):
    id: Slug
    statement: str
    critical: bool = False
    value: float | bool | None = None


class Case(Schema):
    id: Slug
    group: Literal["real", "fictional", "conversation"]
    fixture: Literal["current", "chickens-a", "chickens-b"] = "current"
    court: Slug
    topic: Slug
    question: str = Field(min_length=1)
    # User turns sent before ``question`` on the same thread. Their replies
    # are recorded as context for the judge; only the final answer is graded.
    history: list[str] = Field(default_factory=list)
    references: list[str] = Field(min_length=1)
    facts: list[Fact] = Field(min_length=1)
    acceptable_deferral: str
    requires_escalation: bool = False
    # The reply ends mid-interview: information first, then one question.
    expects_one_question: bool = False
    review_status: str = (
        "draft; checked against repository corpus, not court reviewed"
    )

    @model_validator(mode="after")
    def unique_facts(self) -> Self:
        ids = [fact.id for fact in self.facts]
        if len(ids) != len(set(ids)):
            raise ValueError("Fact IDs must be unique within a case.")
        if any(not turn.strip() for turn in self.history):
            raise ValueError("History turns must not be empty.")
        if bool(self.history) != (self.group == "conversation"):
            raise ValueError(
                "Conversation cases need history; other groups take none."
            )
        return self


class Dimension(Schema):
    score: int = Field(ge=0, le=4, strict=True)
    explanation: str = Field(min_length=1)


class Assessment(Schema):
    fact_id: str
    status: FactStatus
    evidence: str
    value: float | bool | None = None
    explanation: str = ""


class DealBreaker(Schema):
    category: FailureCategory
    evidence: str
    explanation: str = Field(min_length=1)


class Scorecard(Schema):
    dimensions: dict[str, Dimension]
    answer_outcome: Literal["answered", "partial", "deferred"]
    source_attribution: Literal["supported", "absent", "unsupported"]

    @model_validator(mode="after")
    def all_dimensions(self) -> Self:
        if set(self.dimensions) != set(DIMENSIONS):
            raise ValueError("Judge must score all seven dimensions.")
        return self


class Grade(Scorecard):
    facts: list[Assessment]
    deal_breakers: list[DealBreaker]


class CitedAssessment(Schema):
    fact_id: str
    status: FactStatus
    evidence_ids: list[PassageID]
    explanation: str = Field(min_length=1)
    value: float | bool | None


class CitedDealBreaker(Schema):
    category: FailureCategory
    evidence_ids: list[PassageID]
    explanation: str = Field(min_length=1)


class CitedGrade(Scorecard):
    facts: list[CitedAssessment]
    deal_breakers: list[CitedDealBreaker]


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
    references = run / "references"
    binary_hashes = manifest.get("schema_version", 1) >= 2
    if binary_hashes:
        expected_files = set(manifest["reference_hashes"])
        files = {
            str(path.relative_to(references))
            for path in references.rglob("*")
            if path.is_file()
        }
        added = {
            name
            for name in files - expected_files
            if Path(name).name != ".DS_Store"
        }
        if changed := added | (expected_files - files):
            raise ValueError(
                f"Saved reference files changed: {sorted(changed)}"
            )
    for name, expected in manifest["reference_hashes"].items():
        path = references / name
        actual = (
            hashlib.sha256(path.read_bytes()).hexdigest()
            if binary_hashes
            else fingerprint(path.read_text())
        )
        if actual != expected:
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
