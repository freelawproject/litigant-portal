"""
Select published court material for procedural context construction.
"""

import json
from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import JsonValue

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
    from lp_agent.adapters.db import record

    async with db.transaction():
        run = await db.pin_run_context(
            court,
            topic,
            run_id=run_id,
            prompt_keys=prompt_keys,
            prompt_metadata=prompt_metadata,
        )
        conn = db.connection
        manifest = run["manifest"]
        procedures = await (
            await conn.execute(
                """
            SELECT to_jsonb(p) || jsonb_build_object('phases', coalesce((
                SELECT jsonb_agg(to_jsonb(ph) || jsonb_build_object(
                    'facts', coalesce((SELECT jsonb_agg(to_jsonb(pf) || jsonb_build_object('definition', to_jsonb(fd)) ORDER BY pf."order")
                        FROM public.app_topicflowinterviewvariable pf JOIN public.app_variable fd ON fd.id = pf.variable_id WHERE pf.page_id = ph.id), '[]'::jsonb),
                    'documents', coalesce((SELECT jsonb_agg(to_jsonb(pd) ORDER BY pd.position) FROM public.app_phase_document pd WHERE pd.page_id = ph.id), '[]'::jsonb),
                    'deadlines', coalesce((SELECT jsonb_agg(to_jsonb(dl) ORDER BY dl.id) FROM public.app_topicflowdeadline dl WHERE dl.page_id = ph.id), '[]'::jsonb)
                ) ORDER BY ph."order") FROM public.app_topicflowinterviewpage ph WHERE ph.flow_id = p.id
            ), '[]'::jsonb)) AS procedure
            FROM public.app_topicflow p WHERE p.id = ANY(%s::uuid[]) AND p.state = 'published'
            ORDER BY p.slug
        """,
                (list(manifest["procedures"].values()),),
            )
        ).fetchall()
        for row in procedures:
            procedure = record(row["procedure"], "procedure")
            procedure["phases"] = [
                record(phase, "phase") for phase in procedure["phases"]
            ]
            for phase in procedure["phases"]:
                phase["facts"] = [
                    record(fact, "phase_fact") for fact in phase["facts"]
                ]
                for fact in phase["facts"]:
                    fact["definition"] = record(
                        fact["definition"], "fact_definition"
                    )
                phase["documents"] = [
                    record(document) for document in phase["documents"]
                ]
                phase["deadlines"] = [
                    record(deadline, "phase_deadline")
                    for deadline in phase["deadlines"]
                ]
            row["procedure"] = procedure
        documents = await (
            await conn.execute(
                """
            SELECT to_jsonb(d) AS document, coalesce((
                SELECT jsonb_agg(jsonb_build_object('id', ch.id, 'body', ch.body, 'locator', ch.locator) ORDER BY ch.ordinal)
                FROM public.app_document_chunk ch WHERE ch.document_id = d.id
                    AND d.index_state = 'ready' AND d.index_invalidated_at IS NULL
            ), '[]'::jsonb) AS chunks FROM public.app_document d
            WHERE d.id = ANY(%s::uuid[]) AND d.state = 'published' AND d.storage_state = 'available'
                AND d.deleted_at IS NULL
                AND EXISTS (SELECT FROM public.app_corpus_document cd JOIN public.app_document base ON base.id = cd.document_id
                    WHERE cd.court_topic_id = %s AND cd.enabled AND base.key = d.key AND base.owner_court_id = d.owner_court_id)
            ORDER BY d.key
        """,
                (
                    list(manifest["documents"].values()),
                    run["context_court_topic_id"],
                ),
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
            court_topic_id=str(run["context_court_topic_id"]),
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
