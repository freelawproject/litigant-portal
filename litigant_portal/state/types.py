from __future__ import annotations

from datetime import date
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue


class StateModelType(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ComparisonConditionType(StateModelType):
    variable: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    value: bool | int | float | str
    operator: Literal["equals", "not_equals"] = "equals"


class AllConditionType(StateModelType):
    all: list[ConditionType] = Field(min_length=1)


class AnyConditionType(StateModelType):
    any: list[ConditionType] = Field(min_length=1)


class NotConditionType(StateModelType):
    not_: ConditionType = Field(alias="not")


type ConditionType = (
    ComparisonConditionType
    | AllConditionType
    | AnyConditionType
    | NotConditionType
)

AllConditionType.model_rebuild()
AnyConditionType.model_rebuild()
NotConditionType.model_rebuild()


class FactInputType(StateModelType):
    value: JsonValue
    evidence: dict[str, str | None] | None = None


class FactType(FactInputType):
    reviewed: bool = False
    updated_at: AwareDatetime


class StateType(StateModelType):
    identity_id: int
    facts: dict[str, FactType] = Field(default_factory=dict)
    flow_id: UUID | None = None
    viewed: dict[str, str] = Field(default_factory=dict)


class SetFactsActionType(StateModelType):
    kind: Literal["set_facts"] = "set_facts"
    actor: Literal["human", "assistant"]
    facts: dict[str, FactInputType]
    at: AwareDatetime


class ConfirmFactsActionType(StateModelType):
    kind: Literal["confirm_facts"] = "confirm_facts"
    actor: Literal["human"]
    names: tuple[str, ...]
    as_of: AwareDatetime


class MarkViewedActionType(StateModelType):
    kind: Literal["mark_viewed"] = "mark_viewed"
    actor: Literal["human"]
    component_id: str = Field(min_length=1)
    signature: str = Field(pattern=r"^[0-9a-f]{64}$")


type ActionType = Annotated[
    SetFactsActionType | ConfirmFactsActionType | MarkViewedActionType,
    Field(discriminator="kind"),
]


class VariableRuleType(StateModelType):
    required: bool = False
    asked_when: ConditionType | None = None


class _ComponentRuleType(StateModelType):
    id: str = Field(min_length=1)
    content: str
    when: ConditionType | None = None


class InformationRuleType(_ComponentRuleType):
    kind: Literal["information"] = "information"


class QuestionsRuleType(_ComponentRuleType):
    kind: Literal["questions"] = "questions"
    variables: tuple[str, ...] = Field(min_length=1)


class PacketEntryRuleType(StateModelType):
    form: str
    when: ConditionType | None = None


class PacketRuleType(_ComponentRuleType):
    kind: Literal["packet"] = "packet"
    entries: tuple[PacketEntryRuleType, ...] = ()
    interview_available: bool = False


class DeadlineRuleType(StateModelType):
    id: str
    offset_from: str
    offset_days: int
    when: ConditionType | None = None


class CalendarRuleType(_ComponentRuleType):
    kind: Literal["calendar"] = "calendar"
    deadlines: tuple[DeadlineRuleType, ...]


type ComponentRuleType = Annotated[
    InformationRuleType
    | QuestionsRuleType
    | PacketRuleType
    | CalendarRuleType,
    Field(discriminator="kind"),
]


class CourtRulesType(StateModelType):
    flow_id: UUID
    variables: dict[str, VariableRuleType]
    components: tuple[ComponentRuleType, ...]


class DeadlineProjectionType(StateModelType):
    id: str
    date: date | None
    is_past: bool


class ComponentProjectionType(StateModelType):
    id: str
    signature: str
    complete: bool
    can_continue: bool
    variables: tuple[str, ...] = ()


class CandidateType(StateModelType):
    component_id: str
    score: Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)] | None = (
        None
    )


class ProjectionType(StateModelType):
    flow_id: UUID
    as_of: date
    applicable_variables: tuple[str, ...]
    answered: tuple[str, ...]
    missing_required: tuple[str, ...]
    unconfirmed: tuple[str, ...]
    components: tuple[ComponentProjectionType, ...]
    candidates: tuple[CandidateType, ...]
    forms: tuple[str, ...]
    deadlines: tuple[DeadlineProjectionType, ...]
