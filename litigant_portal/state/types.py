from typing import Annotated, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue


class StateModelType(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


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
