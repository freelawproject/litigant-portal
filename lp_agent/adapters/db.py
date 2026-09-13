"""
Trusted operations on the experimental agent tables.

Pass a psycopg AsyncConnection opened with dict_row and autocommit=True.
The caller owns its lifetime and can group operations with conn.transaction().
Catalog writes require a host-authorized author; private operations use the
verified AccessContext. This adapter is never exposed as a model tool.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import LiteralString
from uuid import UUID, uuid4

from jsonschema import Draft202012Validator
from psycopg import AsyncConnection, sql
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb
from pydantic import JsonValue, TypeAdapter

from lp_agent.errors import AgentAccessError, AgentValidationError
from lp_agent.types import (
    AccessContext,
    AgentConfiguration,
    Conversation,
    PromptFragment,
    RunCheckpoint,
    RunOutcome,
    RunRequest,
    RunStatus,
    Scope,
    ScopeSelection,
)
from lp_agent.utils.audit import InstructionArtifact

CATALOG_TABLES = frozenset(
    {
        "court",
        "topic",
        "court_topic",
        "procedure",
        "phase",
        "phase_fact",
        "phase_document",
        "phase_deadline",
        "prompt",
        "fact_definition",
        "corpus_document",
    }
)


class AgentDatabase:
    """
    Ordinary CRUD using driver rows; agent interface methods return contracts.
    """

    def __init__(
        self, connection: AsyncConnection[DictRow], access: AccessContext
    ):
        self.connection = connection
        self.access = access

    async def _one(
        self, query: LiteralString | sql.Composed, params: Sequence[object]
    ) -> DictRow:
        """
        Read one required row within the caller's transaction or a short one.
        """
        async with self.connection.transaction():
            row = await (
                await self.connection.execute(query, params)
            ).fetchone()
            if row is None:
                raise AgentAccessError("Agent record is unavailable.")
            return row

    async def _save(
        self,
        table: str,
        fields: Mapping[str, object],
        record_id: str | None = None,
    ) -> DictRow:
        """
        Share INSERT/UPDATE spelling; callers supply fixed tables and ownership.
        """
        if not fields or "id" in fields:
            raise AgentValidationError("Provide fields without a primary key.")
        columns = list(map(sql.Identifier, fields))
        values = [
            Jsonb(v) if isinstance(v, (dict, list)) else v
            for v in fields.values()
        ]
        if record_id is None:
            query = sql.SQL(
                "INSERT INTO public.{} ({}) VALUES ({}) RETURNING *"
            ).format(
                sql.Identifier("agent_" + table),
                sql.SQL(", ").join(columns),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            )
        else:
            query = sql.SQL(
                "UPDATE public.{} SET {} WHERE id = %s RETURNING *"
            ).format(
                sql.Identifier("agent_" + table),
                sql.SQL(", ").join(
                    sql.SQL("{} = %s").format(c) for c in columns
                ),
            )
            values.append(record_id)
        return await self._one(query, values)

    async def ensure_user(self) -> DictRow:
        """
        Register the host identity without resetting existing recall settings.
        """
        return await self._one(
            """
            INSERT INTO public.agent_user (user_id) VALUES (%s)
            ON CONFLICT (user_id) DO UPDATE SET user_id = EXCLUDED.user_id
            WHERE agent_user.deleted_at IS NULL RETURNING *
        """,
            (self.access.identity_id,),
        )

    async def set_recall(
        self, enabled: bool, limits: dict[str, JsonValue]
    ) -> None:
        """
        Record the user's recall preferences and consent time.
        """
        await self._one(
            """
            UPDATE public.agent_user SET recall_enabled = %s, recall_limits = %s,
                recall_consent_at = now() WHERE user_id = %s AND deleted_at IS NULL
            RETURNING user_id
        """,
            (enabled, Jsonb(limits), self.access.identity_id),
        )

    async def save_catalog(
        self,
        table: str,
        fields: Mapping[str, object],
        *,
        record_id: str | None = None,
    ) -> DictRow:
        """
        Author catalog rows; database constraints protect published revisions.

        Field names are schema columns. This trusted API deliberately has no
        duplicate Python model for every experimental table.
        """
        if table not in CATALOG_TABLES:
            raise AgentValidationError("Unsupported catalog table.")
        values = dict(fields)
        if table == "fact_definition" and "value_schema" in values:
            Draft202012Validator.check_schema(values["value_schema"])
        if table in {"procedure", "prompt"}:
            if record_id is None:
                values["created_by"] = self.access.identity_id
            if values.get("state") == "published":
                values.update(
                    published_by=self.access.identity_id,
                    published_at=datetime.now(UTC),
                )
        return await self._save(table, values, record_id)

    async def catalog_record(self, table: str, record_id: str) -> DictRow:
        """
        Read one catalog record, including a draft for an authorized author.
        """
        if table not in CATALOG_TABLES:
            raise AgentValidationError("Unsupported catalog table.")
        return await self._one(
            sql.SQL("SELECT * FROM public.{} WHERE id = %s").format(
                sql.Identifier("agent_" + table)
            ),
            (record_id,),
        )

    async def delete_catalog_record(self, table: str, record_id: str) -> None:
        """
        Delete an unused catalog row; database references and freezes apply.
        """
        if table not in CATALOG_TABLES:
            raise AgentValidationError("Unsupported catalog table.")
        condition = sql.SQL("true")
        if table in {"prompt", "procedure"}:
            condition = sql.SQL("state IN ('draft', 'in_review')")
        elif table == "phase":
            condition = sql.SQL(
                "procedure_id IN (SELECT id FROM public.agent_procedure WHERE state IN ('draft', 'in_review'))"
            )
        elif table.startswith("phase_"):
            condition = sql.SQL(
                "phase_id IN (SELECT ph.id FROM public.agent_phase ph JOIN public.agent_procedure p ON p.id = ph.procedure_id WHERE p.state IN ('draft', 'in_review'))"
            )
        elif table == "fact_definition":
            raise AgentValidationError(
                "Disable a fact definition instead of deleting it."
            )
        await self._one(
            sql.SQL(
                "DELETE FROM public.{} WHERE id = %s AND {} RETURNING id"
            ).format(
                sql.Identifier("agent_" + table),
                condition,
            ),
            (record_id,),
        )

    async def prompt_fragments(
        self, keys: Sequence[str], metadata: dict[str, JsonValue] | None = None
    ) -> tuple[PromptFragment, ...]:
        """
        Filter the latest published revision of each requested fragment key.
        """
        async with self.connection.transaction():
            rows = await (
                await self.connection.execute(
                    """
                SELECT id::text, key, version, body, metadata FROM (
                    SELECT DISTINCT ON (key) * FROM public.agent_prompt
                    WHERE key = ANY(%s) AND state = 'published'
                    ORDER BY key, version DESC
                ) latest WHERE metadata @> %s ORDER BY key
            """,
                    (list(keys), Jsonb(metadata or {})),
                )
            ).fetchall()
        return tuple(PromptFragment.model_validate(row) for row in rows)

    async def create_matter(self, court_topic_id: str, title: str) -> DictRow:
        """
        Start a separate matter for the current user and a court/topic pair.
        """
        return await self._save(
            "matter",
            {
                "user_id": self.access.identity_id,
                "court_topic_id": court_topic_id,
                "title": title,
            },
        )

    async def matter(self, matter_id: str) -> DictRow:
        """
        Read an owned, available matter.
        """
        return await self._one(
            """
            SELECT m.* FROM public.agent_matter m JOIN public.agent_user u USING (user_id)
            WHERE m.id = %s AND m.user_id = %s AND m.deleted_at IS NULL AND u.deleted_at IS NULL
        """,
            (matter_id, self.access.identity_id),
        )

    async def update_matter(
        self, matter_id: str, *, title: str, closed: bool = False
    ) -> DictRow:
        """
        Rename, close, or reopen an owned matter.
        """
        async with self.connection.transaction():
            await self.matter(matter_id)
            return await self._save(
                "matter",
                {
                    "title": title,
                    "state": "closed" if closed else "open",
                    "closed_at": datetime.now(UTC) if closed else None,
                },
                matter_id,
            )

    async def conversation(self, conversation_id: str) -> DictRow:
        """
        Read an owned conversation and its court/topic slugs.
        """
        return await self._one(
            """
            SELECT c.*, court.slug AS court, topic.slug AS topic
            FROM public.agent_conversation c JOIN public.agent_user u USING (user_id)
            LEFT JOIN public.agent_court court ON court.id = c.court_id
            LEFT JOIN public.agent_topic topic ON topic.id = c.topic_id
            LEFT JOIN public.agent_matter m ON m.id = c.matter_id
            WHERE c.id = %s AND c.user_id = %s AND c.deleted_at IS NULL
                AND u.deleted_at IS NULL AND m.deleted_at IS NULL
        """,
            (conversation_id, self.access.identity_id),
        )

    async def create_conversation(self, scope: ScopeSelection) -> DictRow:
        """
        Start a conversation, preserving partial scope until it is resolved.
        """
        async with self.connection.transaction():
            await self.ensure_user()
            row = await self._save(
                "conversation", {"user_id": self.access.identity_id}
            )
            await self.bind_scope(str(row["id"]), scope)
            return await self.conversation(str(row["id"]))

    async def bind_scope(
        self, conversation_id: str, scope: ScopeSelection
    ) -> None:
        """
        Fill missing scope; the database rejects changes to a bound selection.
        """
        async with self.connection.transaction():
            current = await self.conversation(conversation_id)
            court, topic = (
                scope.court or current["court"],
                scope.topic or current["topic"],
            )
            ids = {}
            for table, slug in (("court", court), ("topic", topic)):
                if slug is not None:
                    row = await self._one(
                        sql.SQL(
                            "SELECT id FROM public.{} WHERE slug = %s AND enabled"
                        ).format(sql.Identifier("agent_" + table)),
                        (slug,),
                    )
                    ids[table + "_id"] = row["id"]
            if len(ids) == 2:
                pair = await self._one(
                    "SELECT id FROM public.agent_court_topic WHERE court_id = %s AND topic_id = %s AND enabled",
                    (ids["court_id"], ids["topic_id"]),
                )
                ids["court_topic_id"] = pair["id"]
            if ids:
                await self._save("conversation", ids, conversation_id)

    async def bind_matter(self, conversation_id: str, matter_id: str) -> None:
        """
        Bind the selected owned matter without creating one implicitly.
        """
        async with self.connection.transaction():
            await self.conversation(conversation_id)
            matter = await self.matter(matter_id)
            pair = await self.catalog_record(
                "court_topic", str(matter["court_topic_id"])
            )
            await self._save(
                "conversation",
                {
                    "matter_id": matter_id,
                    "court_topic_id": pair["id"],
                    "court_id": pair["court_id"],
                    "topic_id": pair["topic_id"],
                },
                conversation_id,
            )

    async def append_item(
        self,
        conversation_id: str,
        *,
        key: str,
        payload: dict[str, JsonValue],
        kind: str = "message",
        origin: str = "user",
        visibility: str = "user",
        run_id: str | None = None,
        step_id: str | None = None,
        search_text: str | None = None,
        attachment_ids: Sequence[str] = (),
    ) -> DictRow:
        """
        Allocate an ordered item once; a reused key must carry the same content.
        """
        async with self.connection.transaction():
            await self.conversation(conversation_id)
            current = await self._one(
                "SELECT next_sequence FROM public.agent_conversation WHERE id = %s FOR UPDATE",
                (conversation_id,),
            )
            values = {
                "conversation_id": UUID(conversation_id),
                "run_id": UUID(run_id) if run_id else None,
                "run_step_id": UUID(step_id) if step_id else None,
                "item_kind": kind,
                "origin": origin,
                "visibility": visibility,
                "context_state": "accepted",
                "payload": payload,
                "search_text": search_text,
                "deduplication_key": key,
            }
            old = await (
                await self.connection.execute(
                    "SELECT * FROM public.agent_conversation_item WHERE conversation_id = %s AND deduplication_key = %s",
                    (conversation_id, key),
                )
            ).fetchone()
            if old:
                attachments = await (
                    await self.connection.execute(
                        "SELECT document_id FROM public.agent_message_attachment WHERE conversation_item_id = %s ORDER BY position",
                        (old["id"],),
                    )
                ).fetchall()
                if any(old[k] != v for k, v in values.items()) or [
                    row["document_id"] for row in attachments
                ] != [UUID(value) for value in attachment_ids]:
                    raise AgentValidationError(
                        "The item key was reused with different content."
                    )
                return old
            row = await self._save(
                "conversation_item",
                {**values, "sequence": current["next_sequence"]},
            )
            for position, document_id in enumerate(attachment_ids, 1):
                await self.document(document_id)
                await self._save(
                    "message_attachment",
                    {
                        "conversation_item_id": row["id"],
                        "document_id": document_id,
                        "position": position,
                    },
                )
            await self.connection.execute(
                "UPDATE public.agent_conversation SET next_sequence = next_sequence + 1 WHERE id = %s",
                (conversation_id,),
            )
            return row

    async def conversation_items(
        self, conversation_id: str, *, after: int = 0, limit: int = 100
    ) -> list[DictRow]:
        """
        Read ordered internal history for the trusted context builder.
        """
        async with self.connection.transaction():
            await self.conversation(conversation_id)
            return await (
                await self.connection.execute(
                    "SELECT * FROM public.agent_conversation_item WHERE conversation_id = %s AND sequence > %s AND redacted_at IS NULL ORDER BY sequence LIMIT %s",
                    (conversation_id, after, min(max(limit, 1), 500)),
                )
            ).fetchall()

    async def create_run(
        self,
        conversation_id: str,
        request: RunRequest,
        configuration: AgentConfiguration,
        *,
        key: str,
    ) -> DictRow:
        """
        Create a run once per request key; reject a changed retry payload.
        """
        if request.conversation_id not in (None, conversation_id):
            raise AgentValidationError("Run conversation does not match.")
        async with self.connection.transaction():
            await self.conversation(conversation_id)
            row = await self._one(
                """
                INSERT INTO public.agent_run (conversation_id, request, configuration, request_key)
                VALUES (%s, %s, %s, %s) ON CONFLICT (conversation_id, request_key)
                DO UPDATE SET request_key = EXCLUDED.request_key RETURNING *
            """,
                (
                    conversation_id,
                    Jsonb(request.model_dump(mode="json")),
                    Jsonb(configuration.model_dump(mode="json")),
                    key,
                ),
            )
            if row["request"] != request.model_dump(mode="json") or row[
                "configuration"
            ] != configuration.model_dump(mode="json"):
                raise AgentValidationError(
                    "The request key was reused with different input."
                )
            return row

    async def run(self, run_id: str) -> DictRow:
        """
        Read a run through its owned conversation.
        """
        async with self.connection.transaction():
            row = await self._one(
                "SELECT * FROM public.agent_run WHERE id = %s", (run_id,)
            )
            await self.conversation(str(row["conversation_id"]))
            return row

    async def save_step(
        self,
        run_id: str,
        *,
        key: str,
        kind: str,
        input: dict[str, JsonValue],
        output: JsonValue = None,
        instructions: InstructionArtifact | None = None,
    ) -> DictRow:
        """
        Record a completed operation and, for model calls, its exact instructions.
        """
        async with self.connection.transaction():
            run = await self.run(run_id)
            await self._one(
                "SELECT id FROM public.agent_conversation WHERE id = %s FOR UPDATE",
                (run["conversation_id"],),
            )
            run = await self._one(
                "SELECT * FROM public.agent_run WHERE id = %s FOR UPDATE",
                (run_id,),
            )
            canonical = (
                instructions.canonical_bytes().decode()
                if instructions
                else None
            )
            old = await (
                await self.connection.execute(
                    "SELECT * FROM public.agent_run_step WHERE run_id = %s AND operation_key = %s AND state = 'completed'",
                    (run_id, key),
                )
            ).fetchone()
            if old:
                if (
                    old["kind"],
                    old["input"],
                    old["output"],
                    old["instruction_canonical_json"],
                ) != (kind, input, output, canonical):
                    raise AgentValidationError(
                        "The step key was reused with different content."
                    )
                return old
            counter = await self._one(
                "SELECT coalesce(max(sequence), 0) + 1 AS next FROM public.agent_run_step WHERE run_id = %s AND attempt = %s",
                (run_id, run["attempt"]),
            )
            fields = {
                "run_id": run_id,
                "attempt": run["attempt"],
                "sequence": counter["next"],
                "operation_key": key,
                "kind": kind,
                "input": input,
                "output": Jsonb(output),
                "state": "completed",
                "finished_at": datetime.now(UTC),
            }
            if instructions is not None:
                fields.update(
                    instruction_format=instructions.format,
                    instruction_canonical_json=canonical,
                    instruction_sha256=instructions.content_hash(),
                )
            return await self._save("run_step", fields)

    async def commit_checkpoint(
        self,
        checkpoint: RunCheckpoint,
        status: RunStatus,
        outcome: RunOutcome | None = None,
    ) -> None:
        """
        Atomically update run state; an unversioned checkpoint is an initial write.

        Carry storage_version from checkpoint() on later writes. Wrap this and
        item/step/fact/progress writes in one connection.transaction() to commit
        them together. A stale version rolls that transaction back.
        """
        for reference in (status, outcome):
            if reference is not None and (
                reference.run_id,
                reference.conversation_id,
            ) != (checkpoint.run_id, checkpoint.conversation_id):
                raise AgentValidationError("Run references must match.")
        if outcome is not None and outcome.state != status.state:
            raise AgentValidationError("Outcome and status must match.")
        async with self.connection.transaction():
            await self.conversation(checkpoint.conversation_id)
            conversation = await self._one(
                "SELECT next_sequence FROM public.agent_conversation WHERE id = %s FOR UPDATE",
                (checkpoint.conversation_id,),
            )
            run = await self._one(
                "SELECT * FROM public.agent_run WHERE id = %s AND conversation_id = %s FOR UPDATE",
                (checkpoint.run_id, checkpoint.conversation_id),
            )
            if run["lock_version"] != (checkpoint.storage_version or 0) or run[
                "state"
            ] in {"completed", "failed", "cancelled"}:
                raise AgentValidationError(
                    "Run state changed; reload the checkpoint before writing."
                )
            await self.connection.execute(
                """
                UPDATE public.agent_run SET state = %s, pending_question = %s,
                    outcome = %s, finished_at = CASE WHEN %s THEN now() ELSE NULL END,
                    checkpoint_sequence = checkpoint_sequence + 1, lock_version = lock_version + 1,
                    checkpoint_format_version = %s, checkpoint_attempt = attempt,
                    checkpoint_conversation_sequence = %s, checkpoint_data = %s
                WHERE id = %s
            """,
                (
                    status.state,
                    Jsonb(status.pending_question.model_dump(mode="json"))
                    if status.pending_question
                    else None,
                    Jsonb(outcome.model_dump(mode="json"))
                    if outcome
                    else None,
                    outcome is not None,
                    checkpoint.version,
                    conversation["next_sequence"] - 1,
                    Jsonb(checkpoint.data),
                    checkpoint.run_id,
                ),
            )

    async def document(self, document_id: str) -> DictRow:
        """
        Read a court document or a document owned by the current live user.
        """
        return await self._one(
            """
            SELECT d.* FROM public.agent_document d
            WHERE d.id = %s AND d.deleted_at IS NULL AND (d.owner_kind = 'court' OR
                (d.owner_user_id = %s AND EXISTS (SELECT FROM public.agent_user u WHERE u.user_id = d.owner_user_id AND u.deleted_at IS NULL)))
        """,
            (document_id, self.access.identity_id),
        )

    async def save_document(
        self,
        fields: Mapping[str, object],
        *,
        record_id: str | None = None,
        court_id: str | None = None,
    ) -> DictRow:
        """
        Record an existing file's metadata; the caller supplies its storage reference.
        """
        async with self.connection.transaction():
            values = dict(fields)
            if record_id is not None:
                await self.document(record_id)
            else:
                values.update(
                    owner_kind="court" if court_id else "user",
                    owner_court_id=court_id,
                    owner_user_id=None
                    if court_id
                    else self.access.identity_id,
                    created_by=self.access.identity_id,
                )
            if values.get("state") == "published":
                values.update(
                    published_by=self.access.identity_id,
                    published_at=datetime.now(UTC),
                )
            return await self._save("document", values, record_id)

    async def link_document(self, matter_id: str, document_id: str) -> DictRow:
        """
        Associate an owned matter with a private document family anchor.
        """
        async with self.connection.transaction():
            await self.matter(matter_id)
            await self.document(document_id)
            return await self._one(
                "INSERT INTO public.agent_matter_document (matter_id, document_id) VALUES (%s, %s) ON CONFLICT (matter_id, document_id) DO UPDATE SET note = agent_matter_document.note RETURNING *",
                (matter_id, document_id),
            )

    async def replace_document_text(
        self,
        document_id: str,
        chunks: Sequence[tuple[str, dict[str, JsonValue]]],
        *,
        parser_version: str,
        chunker_version: str,
    ) -> None:
        """
        Atomically replace supplied text/locators; no extraction or embeddings run.
        """
        async with self.connection.transaction():
            await self.document(document_id)
            await self._one(
                "SELECT id FROM public.agent_document WHERE id = %s FOR UPDATE",
                (document_id,),
            )
            await self.connection.execute(
                "DELETE FROM public.agent_document_chunk WHERE document_id = %s",
                (document_id,),
            )
            async with self.connection.cursor() as cursor:
                await cursor.executemany(
                    "INSERT INTO public.agent_document_chunk (document_id, ordinal, body, locator, text_sha256) VALUES (%s, %s, %s, %s, %s)",
                    [
                        (
                            document_id,
                            i,
                            body,
                            Jsonb(locator),
                            sha256(body.encode()).hexdigest(),
                        )
                        for i, (body, locator) in enumerate(chunks, 1)
                    ],
                )
            await self.connection.execute(
                """
                UPDATE public.agent_document SET index_revision = index_revision + 1,
                    index_state = 'ready', parser_version = %s, chunker_version = %s,
                    chunk_count = %s, indexed_at = now(), index_invalidated_at = NULL,
                    index_error_code = NULL WHERE id = %s
            """,
                (parser_version, chunker_version, len(chunks), document_id),
            )

    async def facts(self, matter_id: str | None = None) -> list[DictRow]:
        """
        Read active personal facts or facts for one owned matter.
        """
        async with self.connection.transaction():
            if matter_id is not None:
                await self.matter(matter_id)
            return await (
                await self.connection.execute(
                    "SELECT a.* FROM public.agent_fact_assertion a JOIN public.agent_user u USING (user_id) WHERE a.user_id = %s AND u.deleted_at IS NULL AND matter_id IS NOT DISTINCT FROM %s::uuid AND state = 'active' AND invalidated_at IS NULL ORDER BY observed_at, id",
                    (self.access.identity_id, matter_id),
                )
            ).fetchall()

    async def record_fact(
        self,
        definition_id: str,
        value: JsonValue,
        *,
        matter_id: str | None = None,
        evidence_kind: str = "user_statement",
        supersedes_id: str | None = None,
    ) -> DictRow:
        """
        Validate a fact with its stored JSON schema and record a new assertion.
        """
        async with self.connection.transaction():
            if matter_id is not None:
                await self.matter(matter_id)
            definition = await self.catalog_record(
                "fact_definition", definition_id
            )
            if not definition["enabled"]:
                raise AgentValidationError("Fact definition is unavailable.")
            Draft202012Validator(definition["value_schema"]).validate(value)
            row = await self._save(
                "fact_assertion",
                {
                    "user_id": self.access.identity_id,
                    "matter_id": matter_id,
                    "fact_definition_id": definition_id,
                    "value": Jsonb(value),
                    "evidence_kind": evidence_kind,
                    "supersedes_id": supersedes_id,
                },
            )
            if supersedes_id:
                await self.connection.execute(
                    "UPDATE public.agent_fact_assertion SET state = 'superseded' WHERE id = %s AND user_id = %s",
                    (supersedes_id, self.access.identity_id),
                )
            return row

    async def fact_evidence(
        self,
        fact_id: str,
        *,
        role: str,
        conversation_item_id: str | None = None,
        document_id: str | None = None,
        run_step_id: str | None = None,
        locator: dict[str, JsonValue] | None = None,
    ) -> DictRow:
        """
        Attach provenance; SQL verifies ownership and exactly one source.
        """
        async with self.connection.transaction():
            await self._one(
                "SELECT id FROM public.agent_fact_assertion WHERE id = %s AND user_id = %s",
                (fact_id, self.access.identity_id),
            )
            return await self._one(
                """
                INSERT INTO public.agent_fact_evidence (fact_assertion_id, role, conversation_item_id, document_id, run_step_id, locator, locator_sha256)
                VALUES (%s, %s, %s, %s, %s, %s, encode(sha256(convert_to(%s::jsonb::text, 'UTF8')), 'hex')) RETURNING *
            """,
                (
                    fact_id,
                    role,
                    conversation_item_id,
                    document_id,
                    run_step_id,
                    Jsonb(locator or {}),
                    Jsonb(locator or {}),
                ),
            )

    async def set_fact_confirmation(self, fact_id: str, state: str) -> None:
        """
        Record confirmation or rejection; searchable confirmations need evidence.
        """
        await self._one(
            "UPDATE public.agent_fact_assertion SET confirmation_state = %s WHERE id = %s AND user_id = %s RETURNING id",
            (state, fact_id, self.access.identity_id),
        )

    async def follow_procedure(
        self, matter_id: str, procedure_id: str
    ) -> DictRow:
        """
        Start following a procedure family within an owned matter.
        """
        async with self.connection.transaction():
            await self.matter(matter_id)
            return await self._one(
                "INSERT INTO public.agent_matter_procedure (matter_id, procedure_id) VALUES (%s, %s) ON CONFLICT (matter_id, procedure_id) DO UPDATE SET state = agent_matter_procedure.state RETURNING *",
                (matter_id, procedure_id),
            )

    async def set_phase_progress(
        self,
        matter_procedure_id: str,
        phase_id: str,
        step_id: str,
        state: str,
        basis: dict[str, JsonValue],
    ) -> DictRow:
        """
        Record progress against the exact phase selected by the run.
        """
        async with self.connection.transaction():
            parent = await self._one(
                "SELECT matter_id FROM public.agent_matter_procedure WHERE id = %s",
                (matter_procedure_id,),
            )
            await self.matter(str(parent["matter_id"]))
            return await self._one(
                """
                INSERT INTO public.agent_phase_progress (matter_procedure_id, phase_id, last_run_step_id, state, basis, started_at, completed_at)
                VALUES (%s, %s, %s, %s, %s, now(), CASE WHEN %s = 'completed' THEN now() END)
                ON CONFLICT (matter_procedure_id, phase_id) DO UPDATE SET state = EXCLUDED.state,
                    basis = EXCLUDED.basis, last_run_step_id = EXCLUDED.last_run_step_id, completed_at = EXCLUDED.completed_at RETURNING *
            """,
                (
                    matter_procedure_id,
                    phase_id,
                    step_id,
                    state,
                    Jsonb(basis),
                    state,
                ),
            )


class DatabaseConversationStore:
    """
    Adapt conversation operations to the existing runtime protocol.
    """

    def __init__(self, connection: AsyncConnection[DictRow]):
        self.connection = connection

    async def create(
        self, *, access: AccessContext, scope: ScopeSelection
    ) -> Conversation:
        db = AgentDatabase(self.connection, access)
        row = await db.create_conversation(scope)
        return await self.get(access=access, conversation_id=str(row["id"]))

    async def get(
        self, *, access: AccessContext, conversation_id: str
    ) -> Conversation:
        row = await AgentDatabase(self.connection, access).conversation(
            conversation_id
        )
        return Conversation(
            conversation_id=str(row["id"]),
            identity_id=row["user_id"],
            scope=ScopeSelection(court=row["court"], topic=row["topic"]),
        )

    async def bind_scope(
        self, *, access: AccessContext, conversation_id: str, scope: Scope
    ) -> None:
        await AgentDatabase(self.connection, access).bind_scope(
            conversation_id,
            ScopeSelection(court=scope.court, topic=scope.topic),
        )


class DatabaseRunStore:
    """
    Adapt persisted runs; checkpoint() supplies the version for the next write.
    """

    def __init__(self, connection: AsyncConnection[DictRow]):
        self.connection = connection

    async def create(
        self,
        *,
        access: AccessContext,
        conversation_id: str,
        request: RunRequest,
        configuration: AgentConfiguration,
    ) -> RunStatus:
        row = await AgentDatabase(self.connection, access).create_run(
            conversation_id, request, configuration, key=str(uuid4())
        )
        return await self.status(access=access, run_id=str(row["id"]))

    async def status(self, *, access: AccessContext, run_id: str) -> RunStatus:
        row = await AgentDatabase(self.connection, access).run(run_id)
        return RunStatus(
            run_id=str(row["id"]),
            conversation_id=str(row["conversation_id"]),
            state=row["state"],
            pending_question=row["pending_question"],
        )

    async def outcome(
        self, *, access: AccessContext, run_id: str
    ) -> RunOutcome | None:
        row = await AgentDatabase(self.connection, access).run(run_id)
        return (
            TypeAdapter(RunOutcome).validate_python(row["outcome"])
            if row["outcome"] is not None
            else None
        )

    async def checkpoint(
        self, *, access: AccessContext, run_id: str
    ) -> RunCheckpoint | None:
        row = await AgentDatabase(self.connection, access).run(run_id)
        if not row["checkpoint_sequence"]:
            return None
        if row["checkpoint_redacted_at"] is not None:
            raise AgentAccessError("Checkpoint is unavailable.")
        return RunCheckpoint(
            run_id=str(row["id"]),
            conversation_id=str(row["conversation_id"]),
            version=row["checkpoint_format_version"],
            storage_version=row["lock_version"],
            data=row["checkpoint_data"],
        )

    async def commit_checkpoint(
        self,
        *,
        access: AccessContext,
        checkpoint: RunCheckpoint,
        status: RunStatus,
        outcome: RunOutcome | None = None,
    ) -> None:
        await AgentDatabase(self.connection, access).commit_checkpoint(
            checkpoint, status, outcome
        )
