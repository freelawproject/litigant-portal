"""
Typed preparation material and scoped services, independent of database drivers.
"""

import json
from contextlib import AbstractAsyncContextManager
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from lp_agent.interfaces import RunStore
from lp_agent.types import (
    AgentConfiguration,
    Choice,
    DatabaseCorpus,
    FunctionCallOutput,
    ModelItem,
    RunRequest,
    RunStatus,
    ScopeSelection,
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
    triage: "TriageState | None" = None


class CourtChoice(Choice):
    topics: tuple[Choice, ...]


class TriageState(Material):
    field: Literal["court", "topic"]
    choices: tuple[Choice, ...]
    message: str
    user_item_id: str


class PreparedContext(Material):
    status: RunStatus
    scope: ScopeSelection
    message: str
    corpus: DatabaseCorpus | None
    procedures: tuple[ProcedureMaterial, ...]
    selected: ProcedureMaterial | None
    history: tuple[ModelItem, ...]
    user_item_id: str
    model_identifier: str
    judge_identifier: str | None = None
    previous: PreparationCheckpoint | None = None
    previous_completed: bool = False
    static_reply: str | None = None
    triage: TriageState | None = None


def source_references(corpus: DatabaseCorpus) -> dict[str, SourceReference]:
    """
    Enumerate actual supplied material, including seeded form excerpts and links.
    """
    sources = {
        document.source.source_id: document.source
        for document in corpus.documents
    }
    settings = corpus.config.get("settings", {})
    locator = (
        settings.get("official_resources_url")
        if isinstance(settings, dict)
        else None
    )
    sources[f"court:{corpus.court_topic_id}"] = SourceReference(
        source_id=f"court:{corpus.court_topic_id}",
        kind="corpus",
        title="Court configuration and contacts",
        locator=locator if isinstance(locator, str) else None,
    )
    for prompt in corpus.prompts:
        if prompt.key == "agent.base":
            continue
        sources[prompt.id] = SourceReference(
            source_id=prompt.id,
            kind="corpus",
            title="Court guidance"
            if prompt.key.startswith("agent.court.")
            else "Topic guidance",
            locator=locator if isinstance(locator, str) else None,
        )
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


def source_material(corpus: DatabaseCorpus) -> list[dict[str, JsonValue]]:
    """
    Associate citation identifiers with the actual evidence supplied to both models.
    """
    bodies: dict[str, list[str]] = {}
    for document in corpus.documents:
        bodies.setdefault(document.source.source_id, []).append(
            document.content
        )
    bodies[f"court:{corpus.court_topic_id}"] = [
        json.dumps(corpus.config, ensure_ascii=False)
    ]
    for prompt in corpus.prompts:
        if prompt.key != "agent.base":
            bodies[prompt.id] = [prompt.body]
    for row in corpus.procedures:
        bodies[str(row["id"])] = [str(row.get("guidance", ""))]
        phases = row.get("phases", [])
        for phase in phases if isinstance(phases, list) else ():
            if isinstance(phase, dict):
                bodies[str(phase["id"])] = [
                    json.dumps(phase, ensure_ascii=False)
                ]
        metadata = row.get("metadata", {})
        if isinstance(metadata, dict):
            forms = metadata.get("form_sources", [])
            for form in forms if isinstance(forms, list) else ():
                if isinstance(form, dict):
                    bodies[str(form["slug"])] = [str(form.get("text", ""))]
    return [
        {
            **source.model_dump(mode="json"),
            "content": "\n\n".join(bodies.get(key, [])),
        }
        for key, source in source_references(corpus).items()
    ]


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

    async def save_static_response(self, text: str) -> None: ...

    async def search(self, name: str, arguments: str) -> JsonValue: ...

    async def discard_response(self) -> None: ...

    async def aclose(self) -> None: ...


class PreparationService(Protocol):
    """
    Open an owned run before static court and topic selection when needed.
    """

    async def open(self, scope: ScopeSelection) -> PreparationSession: ...
