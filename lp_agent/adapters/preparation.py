"""
Preparation persistence on the existing trusted and restricted database surfaces.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from psycopg import AsyncConnection, Error
from psycopg.rows import DictRow
from pydantic import JsonValue, TypeAdapter

from lp_agent.adapters.db import AgentDatabase, DatabaseRunStore
from lp_agent.adapters.session import DatabaseConnections
from lp_agent.corpus.db_search import get_database_corpus
from lp_agent.errors import (
    AgentAccessError,
    AgentStorageError,
    AgentValidationError,
)
from lp_agent.preparation import (
    FactAssertion,
    FactDefinition,
    PhaseBasis,
    PhaseProgress,
    PreparationCheckpoint,
    PreparedContext,
    ProcedureMaterial,
    StoredPreparation,
)
from lp_agent.tools.agent_search import AgentSearch
from lp_agent.types import (
    AccessContext,
    AgentConfiguration,
    FunctionCallOutput,
    ModelItem,
    ModelMessage,
    OutputText,
    Refusal,
    RunRequest,
    Scope,
    ScopeSelection,
)
from lp_agent.utils.audit import InstructionArtifact


class DatabasePreparationSession:
    """
    Own one run's transactions and convert database rows into flow-owned data.
    """

    def __init__(
        self,
        connection: AsyncConnection[DictRow],
        *,
        connections: DatabaseConnections,
        access: AccessContext,
        scope: Scope,
        model_identifier: str,
    ) -> None:
        self._db = AgentDatabase(connection, access)
        self._connections = connections
        self._scope = scope
        self._model_identifier = model_identifier
        self._lookup: AsyncConnection[DictRow] | None = None
        self._context: PreparedContext | None = None
        self._matter_id: str | None = None
        self._followed_id: str | None = None
        self.runs = DatabaseRunStore(connection)

    @property
    def context(self) -> PreparedContext:
        if self._context is None:
            raise RuntimeError("Preparation has not been initialized.")
        return self._context

    @property
    def matter_id(self) -> str:
        if self._matter_id is None:
            raise RuntimeError("Preparation has no matter.")
        return self._matter_id

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        try:
            async with self._db.connection.transaction():
                yield
        except Error:
            raise AgentStorageError() from None

    async def prepare(
        self, request: RunRequest, configuration: AgentConfiguration
    ) -> PreparedContext:
        db = self._db
        selection = ScopeSelection(
            court=self._scope.court, topic=self._scope.topic
        )
        conversation = (
            await db.conversation(request.conversation_id)
            if request.conversation_id
            else await db.create_conversation(selection)
        )
        if (conversation["court"], conversation["topic"]) != (
            selection.court,
            selection.topic,
        ):
            raise AgentAccessError(
                "Start a new conversation to change court or topic."
            )
        if conversation["state"] != "active":
            raise AgentAccessError("This conversation is closed.")
        conversation_id = str(conversation["id"])
        await db.connection.execute(
            "SELECT id FROM public.agent_conversation WHERE id = %s FOR UPDATE",
            (conversation_id,),
        )
        active = await (
            await db.connection.execute(
                "SELECT id FROM public.agent_run WHERE conversation_id = %s AND state IN ('queued', 'running', 'waiting_for_input') LIMIT 1",
                (conversation_id,),
            )
        ).fetchone()
        if active:
            raise AgentValidationError(
                "This conversation already has an active response."
            )
        previous_row = await (
            await db.connection.execute(
                "SELECT checkpoint_data, checkpoint_redacted_at, state FROM public.agent_run WHERE conversation_id = %s ORDER BY created_at DESC, id DESC LIMIT 1",
                (conversation_id,),
            )
        ).fetchone()
        previous = None
        if previous_row:
            if previous_row["checkpoint_redacted_at"] is not None:
                raise AgentAccessError("Conversation context is unavailable.")
            if previous_row["checkpoint_data"] is not None:
                previous = PreparationCheckpoint.model_validate(
                    previous_row["checkpoint_data"]
                )
                if previous.model_identifier != self._model_identifier:
                    raise AgentValidationError(
                        "The model changed. Start a new conversation."
                    )
        if conversation["matter_id"] is None:
            matter = await db.create_matter(
                str(conversation["court_topic_id"]), self._scope.topic
            )
            self._matter_id = str(matter["id"])
            await db.bind_matter(conversation_id, self._matter_id)
        else:
            self._matter_id = str(conversation["matter_id"])
        status = await self.runs.create(
            access=db.access,
            conversation_id=conversation_id,
            request=request,
            configuration=configuration,
        )
        corpus = await get_database_corpus(
            self._scope.court,
            self._scope.topic,
            db=db,
            run_id=status.run_id,
            prompt_keys=(
                "agent.base",
                f"agent.court.{self._scope.court}",
                f"agent.topic.{self._scope.topic}",
            ),
        )
        if not corpus.procedures and not corpus.documents:
            raise AgentValidationError(
                "This court and topic have no available published material."
            )
        expected_prompts = {
            "agent.base",
            f"agent.court.{self._scope.court}",
            f"agent.topic.{self._scope.topic}",
        }
        if not expected_prompts.issubset(
            {prompt.key for prompt in corpus.prompts}
        ):
            raise AgentValidationError(
                "Agent prompt material is unavailable. Load the demo content."
            )
        procedures = tuple(
            ProcedureMaterial.model_validate(row) for row in corpus.procedures
        )
        selected = None
        if previous and previous.procedure_revision:
            selected = next(
                (p for p in procedures if p.id == previous.procedure_revision),
                None,
            )
            if selected is None:
                raise AgentValidationError(
                    "The procedure changed. Start a new conversation."
                )
        user = await db.append_item(
            conversation_id,
            key=f"user:{status.run_id}",
            run_id=status.run_id,
            payload=ModelMessage(
                role="user", content=request.message
            ).model_dump(mode="json"),
            search_text=request.message,
        )
        history: list[ModelItem] = []
        after = 0
        while True:
            rows = await db.conversation_items(
                conversation_id, after=after, limit=500
            )
            history.extend(
                TypeAdapter(ModelItem).validate_python(row["payload"])
                for row in rows
                if row["context_state"] == "accepted"
                and row["origin"] != "framework"
            )
            if len(rows) < 500:
                break
            after = rows[-1]["sequence"]
        self._context = PreparedContext(
            status=status,
            corpus=corpus,
            procedures=procedures,
            selected=selected,
            history=tuple(history),
            user_item_id=str(user["id"]),
            model_identifier=self._model_identifier,
            previous=previous,
            previous_completed=bool(
                previous_row and previous_row["state"] == "completed"
            ),
        )
        return self._context

    async def load_preparation(
        self, procedure: ProcedureMaterial
    ) -> StoredPreparation:
        db = self._db
        # The manifest maps stable procedure families to this run's revisions.
        families = TypeAdapter(dict[str, str]).validate_python(
            self.context.corpus.manifest["procedures"]
        )
        family_id = next(
            (
                key
                for key, revision in families.items()
                if revision == procedure.id
            ),
            None,
        )
        if family_id is None:
            raise AgentAccessError("Procedure is unavailable in this run.")
        followed = await db.follow_procedure(self.matter_id, family_id)
        self._followed_id = str(followed["id"])
        evidence = await (
            await db.connection.execute(
                """
            SELECT DISTINCT e.fact_assertion_id FROM public.agent_fact_evidence e
            JOIN public.agent_conversation_item i ON i.id = e.conversation_item_id
            WHERE e.role = 'basis' AND i.conversation_id = %s
                AND i.context_state = 'accepted' AND i.redacted_at IS NULL
                AND i.origin = 'user'
            """,
                (self.context.status.conversation_id,),
            )
        ).fetchall()
        permitted = {str(row["fact_assertion_id"]) for row in evidence}
        definitions = {
            fact.definition.id: fact.definition.key
            for phase in procedure.phases
            for fact in phase.facts
        }
        rows = [*await db.facts(), *await db.facts(self.matter_id)]
        assertions = {
            definitions[str(row["fact_definition_id"])]: FactAssertion(
                id=str(row["id"]),
                value=row["value"],
                confirmation_state=row["confirmation_state"],
            )
            for row in rows
            if str(row["id"]) in permitted
            and str(row["fact_definition_id"]) in definitions
            and row["confirmation_state"] != "rejected"
        }
        progress = await (
            await db.connection.execute(
                """
                SELECT phase_id, basis, EXISTS (
                    SELECT FROM public.agent_conversation_item i
                    WHERE i.id::text = pp.basis->>'user_item_id'
                        AND i.conversation_id = %s AND i.origin = 'user'
                        AND i.context_state = 'accepted' AND i.redacted_at IS NULL
                ) AS acknowledgement_available
                FROM public.agent_phase_progress pp WHERE matter_procedure_id = %s
                """,
                (self.context.status.conversation_id, self._followed_id),
            )
        ).fetchall()
        return StoredPreparation(
            assertions=assertions,
            bases={
                str(row["phase_id"]): PhaseBasis.model_validate(
                    row["basis"]
                ).model_copy(
                    update={}
                    if row["acknowledgement_available"]
                    else {"acknowledged": False, "user_item_id": None}
                )
                for row in progress
            },
        )

    async def record_fact(
        self,
        definition: FactDefinition,
        value: JsonValue,
        evidence: str,
        supersedes_id: str | None,
    ) -> None:
        row = await self._db.record_fact(
            definition.id,
            value,
            matter_id=self.matter_id if definition.scope == "matter" else None,
            supersedes_id=supersedes_id,
        )
        await self._db.fact_evidence(
            str(row["id"]),
            role="basis",
            conversation_item_id=self.context.user_item_id,
            locator={"quote": evidence},
        )

    async def confirm_facts(self, fact_ids: tuple[str, ...]) -> None:
        for fact_id in fact_ids:
            await self._db.fact_evidence(
                fact_id,
                role="confirmation",
                conversation_item_id=self.context.user_item_id,
            )
            await self._db.set_fact_confirmation(fact_id, "confirmed")

    async def save_progress(
        self,
        procedure: ProcedureMaterial,
        phases: tuple[PhaseProgress, ...],
        bases: dict[str, PhaseBasis],
        step_id: str,
        complete: bool,
    ) -> None:
        if self._followed_id is None:
            raise RuntimeError("No procedure has been selected.")
        for phase, progress in zip(procedure.phases, phases, strict=True):
            await self._db.set_phase_progress(
                self._followed_id,
                phase.id,
                step_id,
                progress.state,
                bases[phase.id].model_dump(mode="json"),
            )
        await self._db.connection.execute(
            "UPDATE public.agent_matter_procedure SET state = %s, completed_at = %s WHERE id = %s",
            (
                "completed" if complete else "active",
                datetime.now(UTC) if complete else None,
                self._followed_id,
            ),
        )

    async def save_step(
        self,
        *,
        key: str,
        kind: str,
        input: dict[str, JsonValue],
        output: JsonValue = None,
        instructions: InstructionArtifact | None = None,
    ) -> str:
        step = await self._db.save_step(
            self.context.status.run_id,
            key=key,
            kind=kind,
            input=input,
            output=output,
            instructions=instructions,
        )
        return str(step["id"])

    async def save_model_items(
        self, items: tuple[ModelItem, ...], step_id: str, *, visible: bool
    ) -> None:
        for position, item in enumerate(items):
            text = None
            if visible and isinstance(item, ModelMessage):
                text = (
                    item.content
                    if isinstance(item.content, str)
                    else "".join(
                        part.text
                        if isinstance(part, OutputText)
                        else part.refusal
                        for part in item.content
                        if isinstance(part, OutputText | Refusal)
                    )
                )
            await self._db.append_item(
                self.context.status.conversation_id,
                key=f"model:{step_id}:{position}",
                run_id=self.context.status.run_id,
                step_id=step_id,
                payload=item.model_dump(mode="json"),
                kind=item.type,
                origin="model",
                visibility="user" if text is not None else "internal",
                search_text=text,
            )

    async def save_tool_output(
        self, output: FunctionCallOutput, step_id: str
    ) -> None:
        await self._db.append_item(
            self.context.status.conversation_id,
            key=f"tool-output:{step_id}",
            run_id=self.context.status.run_id,
            step_id=step_id,
            payload=output.model_dump(mode="json"),
            kind=output.type,
            origin="tool",
            visibility="internal",
        )

    async def save_context(self, item: ModelMessage) -> None:
        await self._db.append_item(
            self.context.status.conversation_id,
            key=f"context:{self.context.status.run_id}",
            run_id=self.context.status.run_id,
            payload=item.model_dump(mode="json"),
            kind="context",
            origin="framework",
            visibility="internal",
        )

    async def search(self, name: str, arguments: str) -> JsonValue:
        if self._lookup is None:
            self._lookup = await self._connections.connect(lookup=True)
        search = AgentSearch(
            self._lookup,
            access=self._db.access,
            run_id=self.context.status.run_id,
            host_policy={
                "matter_ids": [self.matter_id],
                "include_user_facts": True,
            },
        )
        return list(await search.call(name, arguments))

    async def discard_response(self) -> None:
        await self._db.connection.execute(
            "UPDATE public.agent_conversation_item SET context_state = 'superseded' WHERE run_id = %s AND origin <> 'user'",
            (self.context.status.run_id,),
        )

    async def aclose(self) -> None:
        try:
            if self._lookup is not None:
                await self._lookup.close()
        finally:
            await self._db.connection.close()
