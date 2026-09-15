"""
Typed preparation material and scoped services, independent of database drivers.
"""

from contextlib import AbstractAsyncContextManager
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from lp_agent.interfaces import RunStore
from lp_agent.types import (
    AgentConfiguration,
    DatabaseCorpus,
    FunctionCallOutput,
    ModelItem,
    ModelMessage,
    RunRequest,
    RunStatus,
    SourceReference,
)
from lp_agent.utils.audit import InstructionArtifact


class Material(BaseModel):
    """
    Validate the fields consumed by preparation; prompts retain the full corpus.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)


class Condition(Material):
    variable: str
    value: JsonValue
    operator: Literal["equals", "not_equals"] = "equals"

    def matches(self, facts: dict[str, JsonValue]) -> bool:
        if self.variable not in facts or facts[self.variable] is None:
            return False
        equal = facts[self.variable] == self.value
        return equal if self.operator == "equals" else not equal


class FactDefinition(Material):
    id: str
    key: str
    scope: Literal["user", "matter"]
    value_schema: dict[str, JsonValue]


class PhaseFact(Material):
    definition: FactDefinition
    required: bool
    condition: Condition | None = None


class PhaseMaterial(Material):
    id: str
    key: str
    title: str
    facts: tuple[PhaseFact, ...]


class ResourceLink(Material):
    label: str = ""
    name: str = ""
    url: str


class PacketItem(Material):
    form: str
    when: Condition | None = None


class FormMapping(Material):
    name: str


class FormSource(Material):
    slug: str
    mapping: FormMapping


class ProcedureMetadata(Material):
    public_flow_url: str | None = None
    packet: tuple[PacketItem, ...] = ()
    links: tuple[ResourceLink, ...] = ()
    form_sources: tuple[FormSource, ...] = ()


class ProcedureMaterial(Material):
    id: str
    slug: str
    title: str
    phases: tuple[PhaseMaterial, ...]
    metadata: ProcedureMetadata


class CorpusSettings(Material):
    resources: tuple[ResourceLink, ...] = ()


class FactAssertion(Material):
    id: str
    value: JsonValue
    confirmation_state: Literal["unconfirmed", "confirmed", "rejected"]


class PhaseBasis(Material):
    acknowledged: bool = False
    user_item_id: str | None = None
    fact_ids: tuple[str, ...] = ()
    missing: tuple[str, ...] = ()


class StoredPreparation(Material):
    assertions: dict[str, FactAssertion] = Field(default_factory=dict)
    bases: dict[str, PhaseBasis] = Field(default_factory=dict)


class PhaseProgress(Material):
    key: str
    title: str
    state: Literal["completed", "active", "not_started"]
    missing: tuple[str, ...]
    acknowledgement_required: bool


class PreparationSnapshot(Material):
    procedure: str | None = None
    title: str | None = None
    phases: tuple[PhaseProgress, ...] = ()
    facts: dict[str, JsonValue] = Field(default_factory=dict)
    current_phase: PhaseProgress | None = None
    complete: bool = False
    percent_complete: int = 0
    packet: tuple[str, ...] = ()
    resources: tuple[ResourceLink, ...] = ()


class PreparationCheckpoint(Material):
    model_identifier: str
    procedure_revision: str | None = None
    progress: PreparationSnapshot = Field(default_factory=PreparationSnapshot)


class PreparedContext(Material):
    status: RunStatus
    corpus: DatabaseCorpus
    procedures: tuple[ProcedureMaterial, ...]
    selected: ProcedureMaterial | None
    history: tuple[ModelItem, ...]
    user_item_id: str
    model_identifier: str
    previous: PreparationCheckpoint | None = None
    previous_completed: bool = False


def source_references(corpus: DatabaseCorpus) -> dict[str, SourceReference]:
    """
    Enumerate actual supplied material, including seeded form excerpts and links.
    """
    sources = {
        document.source.source_id: document.source
        for document in corpus.documents
    }
    for row in corpus.procedures:
        procedure = ProcedureMaterial.model_validate(row)
        for source_id, title in (
            (procedure.id, procedure.title),
            *((phase.id, phase.title) for phase in procedure.phases),
        ):
            sources[source_id] = SourceReference(
                source_id=source_id,
                kind="corpus",
                title=title,
                locator=procedure.metadata.public_flow_url,
            )
        for form in procedure.metadata.form_sources:
            locator = next(
                (
                    link.url
                    for link in procedure.metadata.links
                    if (link.label or link.name) == form.mapping.name
                ),
                procedure.metadata.public_flow_url,
            )
            sources[form.slug] = SourceReference(
                source_id=form.slug,
                kind="corpus",
                title=form.mapping.name,
                locator=locator,
            )
    return sources


class PreparationSession(Protocol):
    """
    One run's authorized unit of work; never shares a transaction with another run.
    """

    @property
    def runs(self) -> RunStore: ...

    def transaction(self) -> AbstractAsyncContextManager[None]: ...

    async def prepare(
        self, request: RunRequest, configuration: AgentConfiguration
    ) -> PreparedContext: ...

    async def load_preparation(
        self, procedure: ProcedureMaterial
    ) -> StoredPreparation: ...

    async def record_fact(
        self,
        definition: FactDefinition,
        value: JsonValue,
        evidence: str,
        supersedes_id: str | None,
    ) -> None: ...

    async def confirm_facts(self, fact_ids: tuple[str, ...]) -> None: ...

    async def save_progress(
        self,
        procedure: ProcedureMaterial,
        phases: tuple[PhaseProgress, ...],
        bases: dict[str, PhaseBasis],
        step_id: str,
        complete: bool,
    ) -> None: ...

    async def save_step(
        self,
        *,
        key: str,
        kind: str,
        input: dict[str, JsonValue],
        output: JsonValue = None,
        instructions: InstructionArtifact | None = None,
    ) -> str: ...

    async def save_model_items(
        self, items: tuple[ModelItem, ...], step_id: str, *, visible: bool
    ) -> None: ...

    async def save_tool_output(
        self, output: FunctionCallOutput, step_id: str
    ) -> None: ...

    async def save_context(self, item: ModelMessage) -> None: ...

    async def search(self, name: str, arguments: str) -> JsonValue: ...

    async def discard_response(self) -> None: ...

    async def aclose(self) -> None: ...


class PreparationService(Protocol):
    """
    Open a run's services after identity, court, and topic have been bound.
    """

    async def open(self) -> PreparationSession: ...
