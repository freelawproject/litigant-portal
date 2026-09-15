"""
Evidence-backed facts and deterministic progress over typed preparation material.
"""

from pydantic import JsonValue

from lp_agent.errors import AgentValidationError
from lp_agent.flows.checks import AgentChecker
from lp_agent.preparation import (
    CorpusSettings,
    FactAssertion,
    FactDefinition,
    PhaseBasis,
    PhaseProgress,
    PreparationSession,
    PreparationSnapshot,
    PreparedContext,
    ResourceLink,
)


class ProcedureState:
    """
    Calculate preparation state; persistence stays behind scoped service operations.
    """

    def __init__(
        self, session: PreparationSession, context: PreparedContext
    ) -> None:
        self.session = session
        self.context = context
        self.procedure = context.selected
        self.assertions: dict[str, FactAssertion] = {}
        self.phases: tuple[PhaseProgress, ...] = ()
        self._saved: dict[str, PhaseBasis] = {}

    @property
    def definitions(self) -> dict[str, FactDefinition]:
        return (
            {
                fact.definition.key: fact.definition
                for phase in self.procedure.phases
                for fact in phase.facts
            }
            if self.procedure
            else {}
        )

    @property
    def facts(self) -> dict[str, JsonValue]:
        return {key: row.value for key, row in self.assertions.items()}

    async def refresh(self) -> None:
        if self.procedure is None:
            self.assertions, self._saved, self.phases = {}, {}, ()
            return
        stored = await self.session.load_preparation(self.procedure)
        self.assertions = dict(stored.assertions)
        self._saved = dict(stored.bases)
        fact_ids = {row.id for row in self.assertions.values()}
        for phase in self.procedure.phases:
            basis = self._saved.get(phase.id)
            if (
                phase.key == "review"
                and basis
                and set(basis.fact_ids) != fact_ids
            ):
                self._saved.pop(phase.id)
        self._calculate()

    async def select(self, slug: str) -> None:
        if self.procedure is not None:
            raise AgentValidationError(
                "Start a new conversation to change procedure."
            )
        procedure = next(
            (p for p in self.context.procedures if p.slug == slug), None
        )
        if procedure is None or not procedure.phases:
            raise AgentValidationError(
                "Choose an available preparation procedure for this court and topic."
            )
        self.procedure = procedure
        await self.refresh()

    def _calculate(self) -> None:
        phases: list[PhaseProgress] = []
        preceding_complete = True
        for phase in self.procedure.phases if self.procedure else ():
            missing = AgentChecker.phase_requirements(phase, self.facts)
            saved = self._saved.get(phase.id, PhaseBasis())
            automatic = any(fact.required for fact in phase.facts)
            complete = (
                preceding_complete
                and not missing
                and (automatic or saved.acknowledged)
            )
            phases.append(
                PhaseProgress(
                    key=phase.key,
                    title=phase.title,
                    state="completed"
                    if complete
                    else "active"
                    if preceding_complete
                    else "not_started",
                    missing=missing,
                    acknowledgement_required=not automatic,
                )
            )
            preceding_complete = complete
        self.phases = tuple(phases)

    @property
    def current(self) -> PhaseProgress | None:
        return next(
            (phase for phase in self.phases if phase.state == "active"), None
        )

    def resources(self) -> tuple[tuple[str, ...], tuple[ResourceLink, ...]]:
        settings = CorpusSettings.model_validate(
            self.context.corpus.config.get("settings", {})
        )
        links = list(settings.resources)
        packet: tuple[str, ...] = ()
        if self.procedure:
            metadata = self.procedure.metadata
            links = [*metadata.links, *links]
            packet = tuple(
                item.form
                for item in metadata.packet
                if item.when is None or item.when.matches(self.facts)
            )
            if metadata.public_flow_url:
                links.insert(
                    0,
                    ResourceLink(
                        label="Preparation guide and forms",
                        url=metadata.public_flow_url,
                    ),
                )
        result: list[ResourceLink] = []
        seen: set[str] = set()
        for link in links:
            url = link.url
            if url in seen or not (
                url.startswith("https://")
                or (url.startswith("/") and not url.startswith("//"))
            ):
                continue
            seen.add(url)
            result.append(
                ResourceLink(label=link.label or link.name or url, url=url)
            )
        return packet, tuple(result)

    def snapshot(self) -> PreparationSnapshot:
        packet, resources = self.resources()
        complete, percent = AgentChecker.check_finished(self.phases)
        return PreparationSnapshot(
            procedure=self.procedure.slug if self.procedure else None,
            title=self.procedure.title if self.procedure else None,
            phases=self.phases,
            facts=self.facts,
            current_phase=self.current,
            complete=complete,
            percent_complete=percent,
            packet=packet,
            resources=resources,
        )

    def reopen_review(self) -> None:
        for phase in self.procedure.phases if self.procedure else ():
            if phase.key == "review":
                self._saved.pop(phase.id, None)
        self._calculate()

    async def acknowledge(self, key: str) -> None:
        current = self.current
        if self.procedure is None or current is None or key != current.key:
            raise AgentValidationError(
                "Only the current phase can be acknowledged."
            )
        if current.missing:
            raise AgentValidationError("Required facts are still missing.")
        if any(
            basis.user_item_id == self.context.user_item_id
            for basis in self._saved.values()
        ):
            raise AgentValidationError(
                "A separate reply is needed for the next acknowledgement."
            )
        phase = next(
            phase for phase in self.procedure.phases if phase.key == key
        )
        self._saved[phase.id] = PhaseBasis(
            acknowledged=True, user_item_id=self.context.user_item_id
        )
        if key == "review":
            await self.session.confirm_facts(
                tuple(
                    row.id
                    for row in self.assertions.values()
                    if row.confirmation_state != "confirmed"
                )
            )
        self._calculate()

    async def persist(self, step_id: str) -> None:
        if self.procedure is None:
            return
        bases = {
            phase.id: self._saved.get(phase.id, PhaseBasis()).model_copy(
                update={
                    "fact_ids": tuple(
                        row.id for row in self.assertions.values()
                    ),
                    "missing": progress.missing,
                }
            )
            for phase, progress in zip(
                self.procedure.phases, self.phases, strict=True
            )
        }
        await self.session.save_progress(
            self.procedure,
            self.phases,
            bases,
            step_id,
            self.snapshot().complete,
        )
        self._saved = bases
