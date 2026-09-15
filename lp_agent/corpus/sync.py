"""
Publish repository court material into the experimental agent catalog.

Only corpus/ and prompts/ under the application root are read. This publisher
creates no users, conversations, sample answers, or storage objects.
"""

import hashlib
import json
import re
from pathlib import Path

import yaml
from psycopg import sql
from pypdf import PdfReader

from lp_agent.adapters.db import AgentDatabase
from lp_agent.flows.prompts import BASE
from lp_agent.types import AccessContext

AUTHOR = "repository-corpus"


def value_schema(variable):
    """
    Translate the repository variable glossary into fact validation schemas.
    """
    kind = variable.get("data_type", "text")
    schema = {
        "type": {
            "text": "string",
            "date": "string",
            "choice": "string",
            "number": "number",
            "boolean": "boolean",
        }[kind]
    }
    if kind == "choice":
        schema["enum"] = [choice["value"] for choice in variable["choices"]]
    if kind == "date":
        schema["format"] = "date"
    if kind == "text" and variable.get("required"):
        schema["minLength"] = 1
    return schema


async def _latest(db, table, match, *, versioned=False):
    """
    Resolve a catalog natural key without interpolating SQL values.
    """
    query = sql.SQL("SELECT * FROM public.{} WHERE {}{}").format(
        sql.Identifier("agent_" + table),
        sql.SQL(" AND ").join(
            sql.SQL("{} = %s").format(sql.Identifier(key)) for key in match
        ),
        sql.SQL(" ORDER BY version DESC LIMIT 1" if versioned else ""),
    )
    return await (
        await db.connection.execute(query, tuple(match.values()))
    ).fetchone()


async def _catalog(db, table, match, values):
    """
    Upsert unversioned catalog records while retaining stable identifiers.
    """
    row = await _latest(db, table, match)
    if row and all(row[key] == value for key, value in values.items()):
        return row
    return await db.save_catalog(
        table,
        values if row else {**match, **values},
        record_id=str(row["id"]) if row else None,
    )


async def _revision(db, table, match, values):
    """
    Append changed immutable material, returning whether children need copying.
    """
    row = await _latest(db, table, match, versioned=True)
    if (
        row
        and (table == "fact_definition" or row["state"] == "published")
        and all(row[key] == value for key, value in values.items())
    ):
        return row, False
    fields = {
        **match,
        **values,
        "version": row["version"] + 1 if row else 1,
    }
    if table != "fact_definition":
        fields["previous_version_id"] = row["id"] if row else None
        fields["state"] = "draft" if table == "procedure" else "published"
    return await db.save_catalog(table, fields), True


def _phases(flow, variables, definitions):
    """
    Map interview pages to preparation steps and exact fact versions.
    """
    phases = []
    pages = [
        *flow["interview"],
        {
            "title": "Review preparation and next steps",
            "variables": [],
            "review": True,
        },
    ]
    for position, page in enumerate(pages, 1):
        phases.append(
            {
                "key": "review"
                if page.get("review")
                else re.sub(r"[^a-z0-9]+", "-", page["title"].lower()).strip(
                    "-"
                ),
                "position": position,
                "title": page["title"],
                "instructions": page.get("description", "")
                or "Ask for the relevant facts or confirmation of this preparation step.",
                "completion_criteria": [
                    {
                        "type": "required_facts"
                        if any(
                            variables[key].get("required")
                            for key in page["variables"]
                        )
                        else "user_acknowledgement"
                    }
                ],
                "facts": [
                    {
                        "fact_definition_id": str(definitions[key]["id"]),
                        "position": order,
                        "required": variables[key].get("required", False),
                        "condition": variables[key].get("asked_when"),
                    }
                    for order, key in enumerate(page["variables"], 1)
                ],
            }
        )
    return phases


def _material(root, court):
    """
    Read all source files before acquiring the database publication lock.
    """
    variables = {
        item["name"]: item
        for item in yaml.safe_load(
            (root / "corpus/variables.yml").read_text()
        )["variables"]
    }
    courts = sorted((root / "corpus/courts").glob("*/court.yml"))
    if court is not None:
        if court not in {source.parent.name for source in courts}:
            raise ValueError(f"Unknown agent corpus court: {court!r}")
        courts = [source for source in courts if source.parent.name == court]
    sources = []
    forms = {}
    for court_source in courts:
        court_slug = court_source.parent.name
        # Never publish the evaluator's fictional scopes, even if copied into
        # a corpus directory. Evaluation snapshots normally use a separate root.
        if court_slug.startswith("eval-"):
            continue
        court_data = yaml.safe_load(court_source.read_text())
        for topic_source in sorted(
            court_source.parent.glob("topics/*/topic.yml")
        ):
            topic_slug = topic_source.parent.name
            if topic_slug.startswith("eval-"):
                continue
            prompts = {
                f"agent.court.{court_slug}": (
                    root / "prompts/courts" / court_slug / "prompt.md"
                ).read_text(),
                f"agent.topic.{topic_slug}": (
                    root
                    / "prompts/topics"
                    / topic_slug.replace("-", "_")
                    / "prompt.md"
                ).read_text(),
            }
            flows = {}
            for source in sorted(topic_source.parent.glob("flows/*.yml")):
                flow = yaml.safe_load(source.read_text())
                if not flow.get("enabled", True):
                    continue
                for packet in flow.get("packet", []):
                    slug = packet["form"]
                    if slug not in forms:
                        form = root / "corpus/forms" / slug
                        forms[slug] = {
                            "slug": slug,
                            "mapping": yaml.safe_load(
                                form.with_suffix(".yml").read_text()
                            ),
                            "text": "\n".join(
                                page.extract_text() or ""
                                for page in PdfReader(
                                    form.with_suffix(".pdf")
                                ).pages
                            ),
                        }
                flows[source.stem] = flow
            sources.append(
                (
                    court_slug,
                    topic_slug,
                    court_data,
                    yaml.safe_load(topic_source.read_text()),
                    prompts,
                    flows,
                )
            )
    return variables, forms, sources


async def _retire_missing(db, courts, topics, pairs, procedures, prompts):
    """
    Retire removed imported content without deleting history or dependents.
    """
    for table, keep in (("court", courts), ("court_topic", pairs)):
        await db.connection.execute(
            sql.SQL(
                "UPDATE public.{} SET enabled = false "
                "WHERE config->>'managed_by' = %s "
                "AND NOT (id = ANY(%s::uuid[])) AND enabled"
            ).format(sql.Identifier("agent_" + table)),
            (AUTHOR, list(keep)),
        )
    await db.connection.execute(
        """
        UPDATE public.agent_topic t SET enabled = false
        WHERE NOT (t.id = ANY(%s::uuid[])) AND t.enabled
            AND EXISTS (SELECT FROM public.agent_court_topic ct
                WHERE ct.topic_id = t.id AND ct.config->>'managed_by' = %s)
            AND NOT EXISTS (SELECT FROM public.agent_court_topic ct
                WHERE ct.topic_id = t.id AND ct.enabled
                    AND ct.config->>'managed_by' IS DISTINCT FROM %s)
        """,
        (list(topics), AUTHOR, AUTHOR),
    )
    await db.connection.execute(
        """
        UPDATE public.agent_procedure p SET state = 'withdrawn'
        WHERE p.state = 'published'
            AND EXISTS (SELECT FROM public.agent_procedure owned
                WHERE owned.court_topic_id = p.court_topic_id
                    AND owned.slug = p.slug AND owned.created_by = %s)
            AND NOT EXISTS (SELECT FROM public.agent_procedure active
                WHERE active.id = ANY(%s::uuid[])
                    AND active.court_topic_id = p.court_topic_id
                    AND active.slug = p.slug)
        """,
        (AUTHOR, list(procedures)),
    )
    await db.connection.execute(
        """
        UPDATE public.agent_prompt p SET state = 'withdrawn'
        WHERE p.state = 'published' AND NOT (p.key = ANY(%s::text[]))
            AND EXISTS (SELECT FROM public.agent_prompt owned
                WHERE owned.key = p.key AND owned.created_by = %s)
        """,
        (list(prompts), AUTHOR),
    )


async def sync_agent_corpus(
    db: AgentDatabase,
    resource_root: Path,
    *,
    court: str | None = None,
    strict: bool = False,
) -> dict[str, int]:
    """
    Publish repository corpus, retaining unchanged IDs and published revisions.
    """
    variables, forms, sources = _material(Path(resource_root), court)
    db = AgentDatabase(db.connection, AccessContext(identity_id=AUTHOR))
    definitions = {}
    courts, topics, pairs, procedures = set(), set(), set(), set()
    prompts = {"agent.base": BASE}
    phase_count = 0
    async with db.transaction():
        await db.connection.execute("SELECT pg_advisory_xact_lock(173904, 2)")
        for (
            court_slug,
            topic_slug,
            court_data,
            topic_data,
            fragments,
            flows,
        ) in sources:
            court_row = await _catalog(
                db,
                "court",
                {"slug": court_slug},
                {
                    "name": court_data["name"],
                    "jurisdiction_level": court_data["jurisdiction_level"],
                    "config": {**court_data, "managed_by": AUTHOR},
                    "enabled": True,
                },
            )
            topic = await _catalog(
                db,
                "topic",
                {"slug": topic_slug},
                {
                    "title": topic_data["title"],
                    "description": topic_data.get("description", ""),
                    "enabled": True,
                },
            )
            pair = await _catalog(
                db,
                "court_topic",
                {"court_id": court_row["id"], "topic_id": topic["id"]},
                {"config": {"managed_by": AUTHOR}, "enabled": True},
            )
            courts.add(court_row["id"])
            topics.add(topic["id"])
            pairs.add(pair["id"])
            prompts.update(fragments)
            for slug, flow in flows.items():
                for key in sorted(
                    {
                        key
                        for page in flow["interview"]
                        for key in page["variables"]
                    }
                ):
                    if key not in definitions:
                        variable = variables[key]
                        definitions[key], _ = await _revision(
                            db,
                            "fact_definition",
                            {"key": key},
                            {
                                "scope": "user"
                                if variable.get("global")
                                else "matter",
                                "label": variable["label"],
                                "description": variable.get("help_text", ""),
                                "value_schema": value_schema(variable),
                                "enabled": True,
                            },
                        )
                phases = _phases(flow, variables, definitions)
                metadata = {
                    "managed_by": AUTHOR,
                    "public_flow_url": f"/t/{court_slug}/{topic_slug}/{slug}/",
                    "packet": flow.get("packet", []),
                    "links": flow.get("links", []),
                    "form_sources": [
                        forms[packet["form"]]
                        for packet in flow.get("packet", [])
                    ],
                    "phases_sha256": hashlib.sha256(
                        json.dumps(phases, sort_keys=True).encode()
                    ).hexdigest(),
                }
                procedure, created = await _revision(
                    db,
                    "procedure",
                    {"court_topic_id": pair["id"], "slug": slug},
                    {
                        "title": flow["name"],
                        "guidance": "\n\n".join(
                            section["heading"] + "\n" + section["content"]
                            for section in flow["sections"]
                        ),
                        "metadata": metadata,
                    },
                )
                if created:
                    for spec in phases:
                        phase = await db.save_catalog(
                            "phase",
                            {
                                "procedure_id": procedure["id"],
                                **{
                                    key: value
                                    for key, value in spec.items()
                                    if key != "facts"
                                },
                            },
                        )
                        for fact in spec["facts"]:
                            await db.save_catalog(
                                "phase_fact", {"phase_id": phase["id"], **fact}
                            )
                    await db.save_catalog(
                        "procedure",
                        {"state": "published"},
                        record_id=str(procedure["id"]),
                    )
                procedures.add(procedure["id"])
                phase_count += len(phases)
        for key, body in prompts.items():
            await _revision(
                db,
                "prompt",
                {"key": key},
                {"body": body, "metadata": {"managed_by": AUTHOR}},
            )
        if strict:
            await _retire_missing(
                db, courts, topics, pairs, procedures, prompts
            )
    return {
        "courts": len(courts),
        "topics": len(topics),
        "procedures": len(procedures),
        "prompts": len(prompts),
        "fact_definitions": len(definitions),
        "phases": phase_count,
    }
