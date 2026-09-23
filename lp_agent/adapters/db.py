"""
Trusted operations on the experimental agent tables.

Use agent_connection() with host-supplied writer credentials. The caller owns
its lifetime and can group operations with db.transaction().
Catalog writes require a host-authorized author; private operations use the
verified AccessContext. This adapter is never exposed as a model tool.
"""

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from hashlib import sha256
from typing import LiteralString
from uuid import UUID, uuid4

from jsonschema import Draft202012Validator
from psycopg import AsyncConnection, AsyncTransaction, sql
from psycopg.rows import DictRow
from psycopg.types.json import Jsonb
from pydantic import JsonValue, TypeAdapter

from lp_agent.adapters.connections import validate_connection
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

TABLES = {
    "user": "app_useridentity",
    "topic": "app_topic",
    "court": "app_court",
    "court_topic": "app_court_topic",
    "matter": "app_matter",
    "procedure": "app_topicflow",
    "phase": "app_topicflowinterviewpage",
    "phase_fact": "app_topicflowinterviewvariable",
    "phase_deadline": "app_topicflowdeadline",
    "fact_definition": "app_variable",
    "fact_assertion": "app_variableanswer",
    "conversation": "app_chatthread",
    "conversation_item": "app_chatmessage",
    "phase_document": "app_phase_document",
    "prompt": "agent_prompt",
    "document": "app_document",
    "corpus_document": "app_corpus_document",
    "matter_document": "app_matter_document",
    "document_chunk": "app_document_chunk",
    "fact_evidence": "app_fact_evidence",
    "matter_procedure": "app_matter_procedure",
    "phase_progress": "app_phase_progress",
    "memory": "agent_memory",
    "memory_source": "agent_memory_source",
    "message_attachment": "app_message_attachment",
    "run": "agent_run",
    "run_step": "agent_run_step",
}
COLUMNS = {
    "user_id": "identity_id",
    "conversation_id": "thread_id",
    "conversation_item_id": "message_id",
    "procedure_id": "flow_id",
    "phase_id": "page_id",
    "fact_definition_id": "variable_id",
    "fact_assertion_id": "answer_id",
    "payload": "data",
}

FIELDS = {
    "conversation": {"state": "status", "title": "description"},
    "procedure": {"title": "name"},
    "fact_definition": {
        "key": "name",
        "description": "help_text",
        "enabled": "in_schema",
    },
    "phase": {"position": "order"},
    "phase_fact": {"position": "order"},
    "phase_deadline": {"anchor_fact_definition_id": "offset_from_id"},
}


def record(row: DictRow, table: str = "") -> DictRow:
    """
    Preserve the adapter's record keys over the approved shared columns.
    """
    result = dict(row)
    for old, new in (COLUMNS | FIELDS.get(table, {})).items():
        if new in row:
            result[old] = row[new]
    for key in (
        "user_id",
        "owner_user_id",
        "created_by",
        "reviewed_by",
        "published_by",
    ):
        if result.get(key) is not None:
            result[key] = str(result[key])
    if table == "fact_definition":
        result["scope"] = "user" if row["is_global"] else "matter"
    if table == "conversation_item":
        result["visibility"] = (
            "internal" if row["hidden"] or row["meta"] else "user"
        )
    if table in {"phase", "phase_fact"}:
        result["position"] = row["order"] + 1
    if table == "phase_deadline":
        result.update(key=str(row["id"]), rule={"days": row["offset_days"]})
    return result


class AgentDatabase:
    """
    Ordinary CRUD using driver rows; agent interface methods return contracts.
    """

    def __init__(
        self, connection: AsyncConnection[DictRow], access: AccessContext
    ):
        validate_connection(connection)
        self.connection = connection
        self.access = access

    def transaction(self) -> AsyncTransaction:
        """
        Group related writes and their checkpoint in one commit or rollback.

        Let errors escape this block to roll back the whole unit of work.
        Nested adapter transactions use savepoints on this same connection.
        """
        return self.connection.transaction()

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
            return record(row)

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
        original = dict(fields)
        values_by_column = dict(fields)
        if table == "fact_definition" and "scope" in values_by_column:
            values_by_column["is_global"] = (
                values_by_column.pop("scope") == "user"
            )
        if table == "conversation_item" and "visibility" in values_by_column:
            values_by_column["hidden"] = (
                values_by_column.pop("visibility") == "internal"
            )
        if table in {"phase", "phase_fact"} and "position" in values_by_column:
            position = values_by_column["position"]
            if not isinstance(position, int):
                raise AgentValidationError("Position must be an integer.")
            values_by_column["position"] = position - 1
        if table == "procedure" and record_id is None:
            pair = await self.catalog_record(
                "court_topic", str(values_by_column["court_topic_id"])
            )
            values_by_column["topic_id"] = pair["topic_id"]
        if table == "phase_deadline":
            values_by_column.pop("key", None)
            if "rule" in values_by_column:
                rule = values_by_column.pop("rule")
                if (
                    not isinstance(rule, dict)
                    or set(rule) != {"days"}
                    or type(rule["days"]) is not int
                ):
                    raise AgentValidationError(
                        "A deadline rule must contain an integer days offset."
                    )
                values_by_column["offset_days"] = rule["days"]
            phase = await self.catalog_record(
                "phase", str(values_by_column["phase_id"])
            )
            values_by_column["procedure_id"] = phase["procedure_id"]
        if (
            table == "run_step"
            and "instruction_canonical_json" in values_by_column
        ):
            artifact = await self._one(
                "INSERT INTO public.app_promptartifact (id, created_at, updated_at, canonical_format, canonical_payload, content_hash, system_prompt, tool_schemas) VALUES (gen_random_uuid(), now(), now(), %s, %s, %s, '', '[]') ON CONFLICT (content_hash) DO UPDATE SET content_hash = EXCLUDED.content_hash RETURNING id",
                (
                    values_by_column.pop("instruction_format"),
                    values_by_column.pop("instruction_canonical_json"),
                    values_by_column.pop("instruction_sha256"),
                ),
            )
            values_by_column["prompt_artifact_id"] = artifact["id"]
        mapping = COLUMNS | FIELDS.get(table, {})
        fields = {
            mapping.get(key, key): value
            for key, value in values_by_column.items()
        }
        columns = list(map(sql.Identifier, fields))
        values = [
            Jsonb(v) if isinstance(v, dict | list) else v
            for v in fields.values()
        ]
        if record_id is None:
            query = sql.SQL(
                "INSERT INTO public.{} ({}) VALUES ({}) RETURNING *"
            ).format(
                sql.Identifier(TABLES[table]),
                sql.SQL(", ").join(columns),
                sql.SQL(", ").join(sql.Placeholder() for _ in columns),
            )
        else:
            query = sql.SQL(
                "UPDATE public.{} SET {} WHERE id = %s RETURNING *"
            ).format(
                sql.Identifier(TABLES[table]),
                sql.SQL(", ").join(
                    sql.SQL("{} = %s").format(c) for c in columns
                ),
            )
            values.append(record_id)
        row = record(await self._one(query, values), table)
        if table == "run_step":
            row.update(
                {
                    key: original.get(key)
                    for key in (
                        "instruction_format",
                        "instruction_canonical_json",
                        "instruction_sha256",
                    )
                }
            )
        return row

    async def ensure_user(self) -> DictRow:
        """
        Require the live host identity; the adapter does not create identities.
        """
        return await self._one(
            "SELECT *, id AS user_id FROM public.app_useridentity WHERE id = %s AND deleted_at IS NULL",
            (self.access.identity_id,),
        )

    def _require_author(self) -> None:
        """
        Court authoring is a capability supplied only by trusted host code.
        """
        if not self.access.author:
            raise AgentAccessError(
                "Court authoring requires host authorization."
            )

    async def set_recall(
        self, enabled: bool, limits: dict[str, JsonValue]
    ) -> None:
        """
        Record the user's recall preferences and consent time.
        """
        await self._one(
            """
            UPDATE public.app_useridentity SET recall_enabled = %s, recall_limits = %s,
                recall_consent_at = now() WHERE id = %s AND deleted_at IS NULL
            RETURNING id AS user_id
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
        self._require_author()
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
        row = record(
            await self._one(
                sql.SQL("SELECT * FROM public.{} WHERE id = %s").format(
                    sql.Identifier(TABLES[table])
                ),
                (record_id,),
            ),
            table,
        )
        if table in {"procedure", "prompt"} and row["state"] != "published":
            self._require_author()
        if table in {
            "phase",
            "phase_fact",
            "phase_deadline",
            "phase_document",
        }:
            phase = (
                row
                if table == "phase"
                else await self.catalog_record("phase", str(row["phase_id"]))
            )
            await self.catalog_record("procedure", str(phase["procedure_id"]))
        return row

    async def delete_catalog_record(self, table: str, record_id: str) -> None:
        """
        Delete an unused catalog row; database references and freezes apply.
        """
        self._require_author()
        if table not in CATALOG_TABLES:
            raise AgentValidationError("Unsupported catalog table.")
        condition = sql.SQL("true")
        if table in {"prompt", "procedure"}:
            condition = sql.SQL("state IN ('draft', 'in_review')")
        elif table == "phase":
            condition = sql.SQL(
                "flow_id IN (SELECT id FROM public.app_topicflow WHERE state IN ('draft', 'in_review'))"
            )
        elif table.startswith("phase_"):
            condition = sql.SQL(
                "page_id IN (SELECT ph.id FROM public.app_topicflowinterviewpage ph JOIN public.app_topicflow p ON p.id = ph.flow_id WHERE p.state IN ('draft', 'in_review'))"
            )
        elif table == "fact_definition":
            raise AgentValidationError(
                "Disable a fact definition instead of deleting it."
            )
        await self._one(
            sql.SQL(
                "DELETE FROM public.{} WHERE id = %s AND {} RETURNING id"
            ).format(
                sql.Identifier(TABLES[table]),
                condition,
            ),
            (record_id,),
        )

    async def pin_run_context(
        self,
        court: str,
        topic: str,
        *,
        run_id: str,
        prompt_keys: Sequence[str] = (),
        prompt_metadata: dict[str, JsonValue] | None = None,
    ) -> DictRow:
        """
        Validate scope and select a run's initial published revisions once.

        The manifest, configuration and recall policy share one SQL snapshot.
        Return the owned run with its original selection on subsequent calls.
        """
        conn = self.connection
        async with self.transaction():
            run = await self.run(run_id)
            conversation = await self.conversation(str(run["conversation_id"]))
            if (court, topic) != (
                conversation["court"],
                conversation["topic"],
            ) or conversation["matter_id"] is None:
                raise AgentValidationError(
                    "Bind this run to a matter with the requested court and topic."
                )
            scope = await (
                await conn.execute(
                    """
                SELECT ct.id FROM public.app_court_topic ct
                JOIN public.app_court c ON c.id = ct.court_id
                JOIN public.app_topic t ON t.id = ct.topic_id
                WHERE ct.id = %s AND ct.enabled AND c.enabled AND t.enabled
            """,
                    (conversation["court_topic_id"],),
                )
            ).fetchone()
            if scope is None:
                raise AgentAccessError("Court/topic is unavailable.")
            # One statement gives the manifest, configuration and policy the same
            # PostgreSQL snapshot, including when called inside an outer transaction.
            await conn.execute(
                """
                WITH selection AS (
                    SELECT r.id,
                        jsonb_build_object('court', to_jsonb(court), 'topic', to_jsonb(topic),
                            'settings', court.config || ct.config) AS config,
                        u.recall_limits || jsonb_build_object('enabled', coalesce(u.recall_enabled, true)) AS recall,
                        jsonb_build_object(
                            'documents', coalesce((
                                SELECT jsonb_object_agg(base_id::text, id::text) FROM (
                                    SELECT DISTINCT ON (base.id) base.id AS base_id, d.id
                                    FROM public.app_corpus_document cd
                                    JOIN public.app_document base ON base.id = cd.document_id
                                    JOIN public.app_document d ON d.key = base.key AND d.owner_court_id = base.owner_court_id
                                    WHERE cd.court_topic_id = ct.id AND cd.enabled AND d.state = 'published'
                                        AND d.storage_state = 'available' AND d.deleted_at IS NULL
                                    ORDER BY base.id, d.version DESC
                                ) documents
                            ), '{}'::jsonb),
                            'procedures', coalesce((
                                SELECT jsonb_object_agg(base_id::text, id::text) FROM (
                                    SELECT DISTINCT ON (base.id) base.id AS base_id, p.id
                                    FROM public.app_topicflow base JOIN public.app_topicflow p
                                        ON p.court_topic_id = base.court_topic_id AND p.slug = base.slug
                                    WHERE base.court_topic_id = ct.id AND base.version = 1 AND p.state = 'published'
                                    ORDER BY base.id, p.version DESC
                                ) procedures
                            ), '{}'::jsonb),
                            'prompts', coalesce((
                                SELECT jsonb_object_agg(base.id::text, latest.id::text)
                                FROM public.agent_prompt base JOIN (
                                    SELECT DISTINCT ON (key) id, key, metadata FROM public.agent_prompt
                                    WHERE key = ANY(%s) AND state = 'published' ORDER BY key, version DESC
                                ) latest USING (key)
                                WHERE base.version = 1 AND latest.metadata @> %s
                            ), '{}'::jsonb)
                        ) AS manifest
                    FROM public.agent_run r JOIN public.app_chatthread c ON c.id = r.thread_id
                    JOIN public.app_useridentity u ON u.id = c.identity_id
                    JOIN public.app_court_topic ct ON ct.id = c.court_topic_id
                    JOIN public.app_court court ON court.id = ct.court_id
                    JOIN public.app_topic topic ON topic.id = ct.topic_id
                    WHERE r.id = %s AND r.context_selected_at IS NULL
                )
                UPDATE public.agent_run r SET context_court_topic_id = %s, context_format_version = 2,
                    context_selected_at = now(), resolved_config = s.config, recall_policy_snapshot = s.recall,
                    manifest = s.manifest, manifest_sha256 = encode(sha256(convert_to(s.manifest::text, 'UTF8')), 'hex')
                FROM selection s WHERE r.id = s.id AND r.context_selected_at IS NULL
            """,
                (
                    list(prompt_keys),
                    Jsonb(prompt_metadata or {}),
                    run_id,
                    scope["id"],
                ),
            )
            return await self.run(run_id)

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
            SELECT m.* FROM public.app_matter m JOIN public.app_useridentity u ON u.id = m.identity_id
            WHERE m.id = %s AND m.identity_id = %s AND m.deleted_at IS NULL AND u.deleted_at IS NULL
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
            SELECT c.*, c.status AS state, c.description AS title, court.slug AS court, topic.slug AS topic
            FROM public.app_chatthread c JOIN public.app_useridentity u ON u.id = c.identity_id
            LEFT JOIN public.app_court court ON court.id = c.court_id
            LEFT JOIN public.app_topic topic ON topic.id = c.topic_id
            LEFT JOIN public.app_matter m ON m.id = c.matter_id
            WHERE c.id = %s AND c.identity_id = %s AND c.deleted_at IS NULL
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
                        ).format(sql.Identifier(TABLES[table])),
                        (slug,),
                    )
                    ids[table + "_id"] = row["id"]
            if len(ids) == 2:
                pair = await self._one(
                    "SELECT id FROM public.app_court_topic WHERE court_id = %s AND topic_id = %s AND enabled",
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
                "SELECT next_sequence FROM public.app_chatthread WHERE id = %s FOR UPDATE",
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
                    "SELECT * FROM public.app_chatmessage WHERE thread_id = %s AND deduplication_key = %s",
                    (conversation_id, key),
                )
            ).fetchone()
            if old:
                old = record(old, "conversation_item")
                attachments = await (
                    await self.connection.execute(
                        "SELECT document_id FROM public.app_message_attachment WHERE message_id = %s ORDER BY position",
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
                "UPDATE public.app_chatthread SET next_sequence = next_sequence + 1, updated_at = now() WHERE id = %s",
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
            rows = await (
                await self.connection.execute(
                    "SELECT * FROM public.app_chatmessage WHERE thread_id = %s AND sequence > %s AND redacted_at IS NULL ORDER BY sequence LIMIT %s",
                    (conversation_id, after, min(max(limit, 1), 500)),
                )
            ).fetchall()
            return [record(row, "conversation_item") for row in rows]

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
                INSERT INTO public.agent_run (thread_id, request, configuration, request_key)
                VALUES (%s, %s, %s, %s) ON CONFLICT (thread_id, request_key)
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
                "SELECT id FROM public.app_chatthread WHERE id = %s FOR UPDATE",
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
                    "SELECT s.*, p.canonical_payload AS instruction_canonical_json FROM public.agent_run_step s LEFT JOIN public.app_promptartifact p ON p.id = s.prompt_artifact_id WHERE s.run_id = %s AND s.operation_key = %s AND s.state = 'completed'",
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
    ) -> RunCheckpoint:
        """
        Atomically update run state; an unversioned checkpoint is an initial write.

        Return the saved checkpoint with the version for the next write. Wrap
        this and item/step/fact/progress writes in one db.transaction(); only
        use the returned version after that outer transaction commits.
        Let a stale-version error escape the block to roll back all its writes.
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
                "SELECT next_sequence FROM public.app_chatthread WHERE id = %s FOR UPDATE",
                (checkpoint.conversation_id,),
            )
            run = await self._one(
                "SELECT * FROM public.agent_run WHERE id = %s AND thread_id = %s FOR UPDATE",
                (checkpoint.run_id, checkpoint.conversation_id),
            )
            if run["lock_version"] != (checkpoint.storage_version or 0) or run[
                "state"
            ] in {"completed", "failed", "cancelled"}:
                raise AgentValidationError(
                    "Run state changed; reload the checkpoint before writing."
                )
            saved = await self._one(
                """
                UPDATE public.agent_run SET state = %s, pending_question = %s,
                    outcome = %s, finished_at = CASE WHEN %s THEN now() ELSE NULL END,
                    checkpoint_sequence = checkpoint_sequence + 1, lock_version = lock_version + 1,
                    checkpoint_format_version = %s, checkpoint_attempt = attempt,
                    checkpoint_conversation_sequence = %s, checkpoint_data = %s
                WHERE id = %s RETURNING lock_version
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
            return checkpoint.model_copy(
                update={"storage_version": saved["lock_version"]}, deep=True
            )

    async def document(self, document_id: str) -> DictRow:
        """
        Read a court document or a document owned by the current live user.
        """
        return await self._one(
            """
            SELECT d.* FROM public.app_document d
            WHERE d.id = %s AND d.deleted_at IS NULL AND ((d.owner_kind = 'court' AND (%s OR d.state = 'published')) OR
                (d.owner_user_id = %s AND EXISTS (SELECT FROM public.app_useridentity u WHERE u.id = d.owner_user_id AND u.deleted_at IS NULL)))
        """,
            (document_id, self.access.author, self.access.identity_id),
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
            if {
                "owner_kind",
                "owner_user_id",
                "owner_court_id",
            } & values.keys():
                raise AgentValidationError(
                    "Document ownership is fixed by the host."
                )
            if record_id is not None:
                current = await self.document(record_id)
                if current["owner_kind"] == "court":
                    self._require_author()
            elif court_id is not None:
                self._require_author()
            if record_id is None:
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
                "INSERT INTO public.app_matter_document (matter_id, document_id) VALUES (%s, %s) ON CONFLICT (matter_id, document_id) DO UPDATE SET note = app_matter_document.note RETURNING *",
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
            document = await self.document(document_id)
            if document["owner_kind"] == "court":
                self._require_author()
            await self._one(
                "SELECT id FROM public.app_document WHERE id = %s FOR UPDATE",
                (document_id,),
            )
            await self.connection.execute(
                "DELETE FROM public.app_document_chunk WHERE document_id = %s",
                (document_id,),
            )
            async with self.connection.cursor() as cursor:
                await cursor.executemany(
                    "INSERT INTO public.app_document_chunk (document_id, ordinal, body, locator, text_sha256) VALUES (%s, %s, %s, %s, %s)",
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
                UPDATE public.app_document SET index_revision = index_revision + 1,
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
            rows = await (
                await self.connection.execute(
                    "SELECT a.* FROM public.app_variableanswer a JOIN public.app_useridentity u ON u.id = a.identity_id JOIN public.app_variable v ON v.id = a.variable_id WHERE (v.is_global OR a.matter_id IS NOT NULL) AND a.identity_id = %s AND u.deleted_at IS NULL AND matter_id IS NOT DISTINCT FROM %s::uuid AND state = 'active' AND invalidated_at IS NULL ORDER BY a.observed_at, a.id",
                    (self.access.identity_id, matter_id),
                )
            ).fetchall()
            return [record(row) for row in rows]

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
                    "UPDATE public.app_variableanswer SET state = 'superseded' WHERE id = %s AND identity_id = %s",
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
                "SELECT id FROM public.app_variableanswer WHERE id = %s AND identity_id = %s",
                (fact_id, self.access.identity_id),
            )
            return await self._one(
                """
                INSERT INTO public.app_fact_evidence (answer_id, role, message_id, document_id, run_step_id, locator, locator_sha256)
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
            "UPDATE public.app_variableanswer SET confirmation_state = %s, reviewed = (%s = 'confirmed') WHERE id = %s AND identity_id = %s RETURNING id",
            (state, state, fact_id, self.access.identity_id),
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
                "INSERT INTO public.app_matter_procedure (matter_id, flow_id) VALUES (%s, %s) ON CONFLICT (matter_id, flow_id) DO UPDATE SET state = app_matter_procedure.state RETURNING *",
                (matter_id, procedure_id),
            )

    async def set_phase_progress(
        self,
        matter_procedure_id: str,
        phase_id: str,
        step_id: str | None,
        state: str,
        basis: dict[str, JsonValue],
    ) -> DictRow:
        """
        Record progress against the exact phase selected by the run.
        """
        async with self.connection.transaction():
            parent = await self._one(
                "SELECT matter_id FROM public.app_matter_procedure WHERE id = %s",
                (matter_procedure_id,),
            )
            await self.matter(str(parent["matter_id"]))
            return await self._one(
                """
                INSERT INTO public.app_phase_progress (matter_procedure_id, page_id, last_run_step_id, state, basis, started_at, completed_at)
                VALUES (%s, %s, %s, %s, %s, now(), CASE WHEN %s = 'completed' THEN now() END)
                ON CONFLICT (matter_procedure_id, page_id) DO UPDATE SET state = EXCLUDED.state,
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
        validate_connection(connection)
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
    Adapt persisted runs; checkpoint reads and commits return storage versions.
    """

    def __init__(self, connection: AsyncConnection[DictRow]):
        validate_connection(connection)
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
    ) -> RunCheckpoint:
        return await AgentDatabase(self.connection, access).commit_checkpoint(
            checkpoint, status, outcome
        )
