"""
Publish fictional evaluation guides through the new agent's database catalog.
"""

import asyncio
from pathlib import Path

import yaml

from .corpus import MARKER, TOPIC
from .schema import fingerprint

COURT = "eval-ohio"
AUTHOR = "agent-eval-fixtures"
TOPICS = {
    "chickens-a": f"{TOPIC}-a",
    "chickens-b": f"{TOPIC}-b",
}


def scope(case) -> dict:
    """
    Select an isolated topic for each fictional variant, preserving real scopes.
    """
    if case.fixture == "current":
        return {"court": case.court, "topic": case.topic}
    if case.court != COURT or case.topic != TOPIC:
        raise ValueError("Unknown fictional evaluation scope.")
    return {"court": COURT, "topic": TOPICS[case.fixture]}


async def _catalog(db, table: str, match: dict, values: dict):
    """
    Create or update only catalog rows explicitly owned by this evaluator.
    """
    from psycopg import sql

    row = await (
        await db.connection.execute(
            sql.SQL("SELECT * FROM {} WHERE {}").format(
                sql.Identifier("agent_" + table),
                sql.SQL(" AND ").join(
                    sql.SQL("{} = %s").format(sql.Identifier(key))
                    for key in match
                ),
            ),
            tuple(match.values()),
        )
    ).fetchone()
    if row:
        marker = (
            row["description"]
            if table == "topic"
            else row["config"].get("managed_by")
        )
        if marker != MARKER:
            raise ValueError(f"Existing agent {table} is not evaluator-owned.")
        if all(row[key] == value for key, value in values.items()):
            return row
    return await db.save_catalog(
        table,
        values if row else {**match, **values},
        record_id=str(row["id"]) if row else None,
    )


async def _revision(db, table: str, match: dict, values: dict):
    """
    Reuse identical published material or append an immutable revision.
    """
    from psycopg import sql

    row = await (
        await db.connection.execute(
            sql.SQL(
                "SELECT * FROM {} WHERE {} ORDER BY version DESC LIMIT 1"
            ).format(
                sql.Identifier("agent_" + table),
                sql.SQL(" AND ").join(
                    sql.SQL("{} = %s").format(sql.Identifier(key))
                    for key in match
                ),
            ),
            tuple(match.values()),
        )
    ).fetchone()
    if row:
        if row["created_by"] != AUTHOR:
            raise ValueError(f"Existing agent {table} is not evaluator-owned.")
        if row["state"] == "published" and all(
            row[key] == value for key, value in values.items()
        ):
            return row
    return await db.save_catalog(
        table,
        {
            **match,
            **values,
            "version": row["version"] + 1 if row else 1,
            "previous_version_id": row["id"] if row else None,
            "state": "published",
        },
    )


async def publish(db, root: Path, variant: str) -> dict:
    """
    Atomically publish a frozen fixture without changing real court material.
    """
    topic_slug = TOPICS[variant]
    court_path = root / "corpus" / "courts" / COURT
    topic_path = court_path / "topics" / TOPIC
    court_data = yaml.safe_load((court_path / "court.yml").read_text())
    topic_data = yaml.safe_load((topic_path / "topic.yml").read_text())
    flow = yaml.safe_load(
        (topic_path / "flows" / "protection.yml").read_text()
    )
    guidance = "\n\n".join(
        section["heading"] + "\n" + section["content"]
        for section in flow["sections"]
    )
    async with db.transaction():
        # Concurrent evaluators may reuse the same immutable fixture rows.
        await db.connection.execute("SELECT pg_advisory_xact_lock(179, 1888)")
        base = await db.prompt_fragments(("agent.base",))
        if not base:
            raise ValueError(
                "Publish agent.base before evaluating the new agent."
            )
        await db.ensure_user()
        court = await _catalog(
            db,
            "court",
            {"slug": COURT},
            {
                "name": court_data["court_name"],
                "jurisdiction_level": court_data["jurisdiction_level"],
                "config": {**court_data, "managed_by": MARKER},
                "enabled": True,
            },
        )
        topic = await _catalog(
            db,
            "topic",
            {"slug": topic_slug},
            {
                "title": f"{topic_data['title']} ({variant})",
                "description": MARKER,
                "enabled": True,
            },
        )
        pair = await _catalog(
            db,
            "court_topic",
            {"court_id": court["id"], "topic_id": topic["id"]},
            {"config": {"managed_by": MARKER}, "enabled": True},
        )
        prompts = {base[0].key: base[0].id}
        for key, body in (
            (f"agent.court.{COURT}", court_data["court_name"]),
            (f"agent.topic.{topic_slug}", topic_data["title"]),
        ):
            prompt = await _revision(
                db, "prompt", {"key": key}, {"body": body}
            )
            prompts[key] = str(prompt["id"])
        procedure = await _revision(
            db,
            "procedure",
            {"court_topic_id": pair["id"], "slug": "protection"},
            {
                "title": flow["name"],
                "guidance": guidance,
                "metadata": {"managed_by": MARKER, "fixture": variant},
            },
        )
        return {
            "scope": {"court": COURT, "topic": topic_slug},
            "court_topic_id": str(pair["id"]),
            "procedure_id": str(procedure["id"]),
            "procedure_version": procedure["version"],
            "guidance": guidance,
            "guidance_hash": fingerprint(guidance),
            "prompts": prompts,
        }


def install_fixture(root: Path, variant: str) -> dict:
    """
    Use the container's configured writer connection for benchmark setup.
    """
    from lp_agent.adapters.db import AgentDatabase
    from lp_agent.adapters.session import DatabaseConnections
    from lp_agent.types import AccessContext

    async def install():
        async with DatabaseConnections().connection() as connection:
            return await publish(
                AgentDatabase(connection, AccessContext(identity_id=AUTHOR)),
                root,
                variant,
            )

    return asyncio.run(install())
