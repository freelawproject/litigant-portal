"""
Select published court material for procedural context construction.
"""

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import JsonValue

from lp_agent.errors import AgentAccessError, AgentValidationError
from lp_agent.types import (
    CorpusDocument,
    DatabaseCorpus,
    PromptFragment,
    Scope,
    SourceReference,
)

if TYPE_CHECKING:
    from lp_agent.adapters.db import AgentDatabase


async def get_database_corpus(
    court: str,
    topic: str,
    *,
    db: "AgentDatabase",
    run_id: str,
    prompt_keys: Sequence[str] = (),
    prompt_metadata: dict[str, JsonValue] | None = None,
) -> DatabaseCorpus:
    """
    Pin a run's initial selection, then load its available exact revisions.

    Prompt keys/metadata come from Python. They select the initial fragment
    set; subsequent calls use that saved set. Corpus publication changes never
    silently upgrade a running conversation. Withdrawals take effect on reads.
    The consuming flow assembles prompts and adds this material to ModelRequest.
    """
    from psycopg.types.json import Jsonb

    conn = db.connection
    async with conn.transaction():
        run = await db.run(run_id)
        conversation = await db.conversation(str(run["conversation_id"]))
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
            SELECT ct.id FROM public.agent_court_topic ct
            JOIN public.agent_court c ON c.id = ct.court_id
            JOIN public.agent_topic t ON t.id = ct.topic_id
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
                                FROM public.agent_corpus_document cd
                                JOIN public.agent_document base ON base.id = cd.document_id
                                JOIN public.agent_document d ON d.key = base.key AND d.owner_court_id = base.owner_court_id
                                WHERE cd.court_topic_id = ct.id AND cd.enabled AND d.state = 'published'
                                    AND d.storage_state = 'available' AND d.deleted_at IS NULL
                                ORDER BY base.id, d.version DESC
                            ) documents
                        ), '{}'::jsonb),
                        'procedures', coalesce((
                            SELECT jsonb_object_agg(base_id::text, id::text) FROM (
                                SELECT DISTINCT ON (base.id) base.id AS base_id, p.id
                                FROM public.agent_procedure base JOIN public.agent_procedure p
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
                FROM public.agent_run r JOIN public.agent_conversation c ON c.id = r.conversation_id
                JOIN public.agent_user u ON u.user_id = c.user_id
                JOIN public.agent_court_topic ct ON ct.id = c.court_topic_id
                JOIN public.agent_court court ON court.id = ct.court_id
                JOIN public.agent_topic topic ON topic.id = ct.topic_id
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
        run = await db.run(run_id)
        manifest = run["manifest"]
        procedures = await (
            await conn.execute(
                """
            SELECT to_jsonb(p) || jsonb_build_object('phases', coalesce((
                SELECT jsonb_agg(to_jsonb(ph) || jsonb_build_object(
                    'facts', coalesce((SELECT jsonb_agg(to_jsonb(pf) || jsonb_build_object('definition', to_jsonb(fd)) ORDER BY pf.position)
                        FROM public.agent_phase_fact pf JOIN public.agent_fact_definition fd ON fd.id = pf.fact_definition_id WHERE pf.phase_id = ph.id), '[]'::jsonb),
                    'documents', coalesce((SELECT jsonb_agg(to_jsonb(pd) ORDER BY pd.position) FROM public.agent_phase_document pd WHERE pd.phase_id = ph.id), '[]'::jsonb),
                    'deadlines', coalesce((SELECT jsonb_agg(to_jsonb(dl) ORDER BY dl.key) FROM public.agent_phase_deadline dl WHERE dl.phase_id = ph.id), '[]'::jsonb)
                ) ORDER BY ph.position) FROM public.agent_phase ph WHERE ph.procedure_id = p.id
            ), '[]'::jsonb)) AS procedure
            FROM public.agent_procedure p WHERE p.id = ANY(%s::uuid[]) AND p.state = 'published'
            ORDER BY p.slug
        """,
                (list(manifest["procedures"].values()),),
            )
        ).fetchall()
        documents = await (
            await conn.execute(
                """
            SELECT to_jsonb(d) AS document, coalesce((
                SELECT jsonb_agg(jsonb_build_object('id', ch.id, 'body', ch.body, 'locator', ch.locator) ORDER BY ch.ordinal)
                FROM public.agent_document_chunk ch WHERE ch.document_id = d.id
                    AND d.index_state = 'ready' AND d.index_invalidated_at IS NULL
            ), '[]'::jsonb) AS chunks FROM public.agent_document d
            WHERE d.id = ANY(%s::uuid[]) AND d.state = 'published' AND d.storage_state = 'available'
                AND d.deleted_at IS NULL
                AND EXISTS (SELECT FROM public.agent_corpus_document cd JOIN public.agent_document base ON base.id = cd.document_id
                    WHERE cd.court_topic_id = %s AND cd.enabled AND base.key = d.key AND base.owner_court_id = d.owner_court_id)
            ORDER BY d.key
        """,
                (list(manifest["documents"].values()), scope["id"]),
            )
        ).fetchall()
        prompts = await (
            await conn.execute(
                "SELECT id::text, key, version, body, metadata FROM public.agent_prompt WHERE id = ANY(%s::uuid[]) AND state = 'published' ORDER BY key",
                (list(manifest["prompts"].values()),),
            )
        ).fetchall()
        return DatabaseCorpus(
            scope=Scope(court=court, topic=topic),
            court_topic_id=str(scope["id"]),
            config=run["resolved_config"],
            manifest=manifest,
            procedures=tuple(row["procedure"] for row in procedures),
            document_records=tuple(row["document"] for row in documents),
            prompts=tuple(
                PromptFragment.model_validate(row) for row in prompts
            ),
            documents=tuple(
                CorpusDocument(
                    content=chunk["body"],
                    source=SourceReference(
                        source_id=row["document"]["id"],
                        kind="corpus",
                        title=row["document"]["title"],
                        locator=json.dumps(
                            {
                                "chunk_id": chunk["id"],
                                "index_revision": row["document"][
                                    "index_revision"
                                ],
                                "locator": chunk["locator"],
                            }
                        ),
                    ),
                )
                for row in documents
                for chunk in row["chunks"]
            ),
        )
