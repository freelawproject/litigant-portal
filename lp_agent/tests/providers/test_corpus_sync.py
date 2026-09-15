"""
Exercise real-corpus publication and shared QA connections in isolated Postgres.
"""

import asyncio
import shutil
from contextlib import asynccontextmanager

import pytest
import yaml
from django.conf import settings
from django.test import override_settings
from psycopg import Connection, sql
from psycopg.conninfo import conninfo_to_dict

from lp_agent.adapters.connections import agent_connection
from lp_agent.adapters.db import AgentDatabase
from lp_agent.adapters.session import DatabaseConnections
from lp_agent.corpus.db_search import get_database_corpus
from lp_agent.corpus.sync import sync_agent_corpus
from lp_agent.tests.providers import test_database as database_fixtures
from lp_agent.types import (
    AccessContext,
    AgentConfiguration,
    RunRequest,
    ScopeSelection,
)

pytestmark = pytest.mark.postgres
database_dsns = database_fixtures.database_dsns


@pytest.fixture(autouse=True)
def empty_catalog(database_dsns):
    """
    Reset only this module's disposable database between publication scenarios.
    """
    with Connection.connect(database_dsns["admin"]) as connection:
        names = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
        connection.execute(
            sql.SQL("TRUNCATE {} RESTRICT").format(
                sql.SQL(", ").join(
                    sql.Identifier("public", row[0]) for row in names
                )
            )
        )


@pytest.fixture
def root(tmp_path):
    """
    Copy the source inputs so tests can change corpus without editing the checkout.
    """
    for folder in ("corpus", "prompts"):
        shutil.copytree(settings.BASE_DIR / folder, tmp_path / folder)
    return tmp_path


@asynccontextmanager
async def publisher(database_dsns):
    """
    Open a publisher without creating a sample user.
    """
    async with agent_connection(database_dsns["crud"]) as connection:
        yield AgentDatabase(connection, AccessContext(identity_id="sync-test"))


async def snapshot(db):
    """
    Include timestamps in fingerprints to detect writes on an unchanged import.
    """
    tables = await (
        await db.connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )
    ).fetchall()
    result = {}
    for row in tables:
        result[row["tablename"]] = await (
            await db.connection.execute(
                sql.SQL(
                    "SELECT count(*) AS count, md5(coalesce("
                    "jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text)::text, '[]')) AS hash "
                    "FROM public.{} t"
                ).format(sql.Identifier(row["tablename"]))
            )
        ).fetchone()
    return result


def test_real_corpus_only_and_unchanged_rerun(database_dsns, root):
    fictional = root / "corpus/courts/eval-ohio"
    fictional.mkdir()
    (fictional / "court.yml").write_text("name: Fictional Ohio\n")

    async def scenario():
        async with publisher(database_dsns) as db:
            summary = await sync_agent_corpus(db, root, strict=True)
            assert summary == {
                "courts": 2,
                "topics": 2,
                "procedures": 4,
                "prompts": 5,
                "fact_definitions": 31,
                "phases": 20,
            }
            before = await snapshot(db)
            expected = {
                "agent_court": 2,
                "agent_topic": 2,
                "agent_court_topic": 2,
                "agent_procedure": 4,
                "agent_prompt": 5,
                "agent_fact_definition": 31,
                "agent_phase": 20,
                "agent_phase_fact": 54,
            }
            assert {
                table: row["count"]
                for table, row in before.items()
                if row["count"]
            } == expected
            assert await sync_agent_corpus(db, root, strict=True) == summary
            assert await snapshot(db) == before
            procedures = await (
                await db.connection.execute(
                    "SELECT metadata FROM agent_procedure"
                )
            ).fetchall()
            sources = {
                source["slug"]: source
                for row in procedures
                for source in row["metadata"]["form_sources"]
            }
            assert len(sources) == 8
            assert all(
                source["mapping"] and source["text"].strip()
                for source in sources.values()
            )

    asyncio.run(scenario())


def test_changed_material_keeps_pinned_revisions(database_dsns, root):
    async def scenario():
        async with publisher(database_dsns) as db:
            await sync_agent_corpus(db, root)
            await db.ensure_user()
            conversation = await db.create_conversation(
                ScopeSelection(court="north-dakota", topic="adult-name-change")
            )
            matter = await db.create_matter(
                str(conversation["court_topic_id"]), "Corpus revision test"
            )
            await db.bind_matter(str(conversation["id"]), str(matter["id"]))
            run = await db.create_run(
                str(conversation["id"]),
                RunRequest(message="Prepare my name change"),
                AgentConfiguration(),
                key="initial",
            )
            original = await get_database_corpus(
                "north-dakota",
                "adult-name-change",
                db=db,
                run_id=str(run["id"]),
                prompt_keys=("agent.base", "agent.court.north-dakota"),
            )
            flow_path = (
                root
                / "corpus/courts/north-dakota/topics/adult-name-change/flows/standard.yml"
            )
            flow = yaml.safe_load(flow_path.read_text())
            flow["sections"][0]["content"] += (
                "\nUpdated repository guidance for the test."
            )
            flow_path.write_text(yaml.safe_dump(flow))
            key = flow["interview"][0]["variables"][0]
            variables_path = root / "corpus/variables.yml"
            variables = yaml.safe_load(variables_path.read_text())
            next(
                item for item in variables["variables"] if item["name"] == key
            )["label"] += " (updated)"
            variables_path.write_text(yaml.safe_dump(variables))
            prompt = root / "prompts/courts/north-dakota/prompt.md"
            prompt.write_text(
                prompt.read_text() + "\nUpdated source prompt.\n"
            )
            await sync_agent_corpus(db, root, strict=True)
            pinned = await get_database_corpus(
                "north-dakota",
                "adult-name-change",
                db=db,
                run_id=str(run["id"]),
            )
            assert pinned == original
            revisions = await (
                await db.connection.execute(
                    "SELECT version, state, previous_version_id FROM agent_procedure WHERE slug = 'standard' ORDER BY version"
                )
            ).fetchall()
            assert [row["version"] for row in revisions] == [1, 2]
            assert all(row["state"] == "published" for row in revisions)
            assert revisions[1]["previous_version_id"] is not None
            assert (
                await (
                    await db.connection.execute(
                        "SELECT max(version) AS version FROM agent_fact_definition WHERE key = %s",
                        (key,),
                    )
                ).fetchone()
            )["version"] == 2
            before = await snapshot(db)
            await sync_agent_corpus(db, root, strict=True)
            assert await snapshot(db) == before

    asyncio.run(scenario())


def test_strict_removal_and_court_selection(database_dsns, root):
    async def scenario():
        async with publisher(database_dsns) as db:
            await sync_agent_corpus(db, root)
            (
                root
                / "corpus/courts/north-dakota/topics/adult-name-change/flows/waiver.yml"
            ).unlink()
            await sync_agent_corpus(
                db, root, court="north-dakota", strict=True
            )
            enabled = await db.scope_choices()
            assert [row.choice_id for row in enabled] == ["north-dakota"]
            states = await (
                await db.connection.execute(
                    "SELECT slug, state FROM agent_procedure ORDER BY slug"
                )
            ).fetchall()
            assert {row["slug"]: row["state"] for row in states} == {
                "standard": "published",
                "waiver": "withdrawn",
                "tenant": "withdrawn",
                "landlord": "withdrawn",
            }
            before = await snapshot(db)
            with pytest.raises(ValueError, match="Unknown agent corpus court"):
                await sync_agent_corpus(db, root, court="missing", strict=True)
            assert await snapshot(db) == before

    asyncio.run(scenario())


def test_failed_publication_rolls_back(database_dsns, root, monkeypatch):
    original = AgentDatabase.save_catalog

    async def fail_on_phase(self, table, fields, **kwargs):
        if table == "phase":
            raise RuntimeError("Publication interrupted")
        return await original(self, table, fields, **kwargs)

    monkeypatch.setattr(AgentDatabase, "save_catalog", fail_on_phase)

    async def scenario():
        async with publisher(database_dsns) as db:
            before = await snapshot(db)
            with pytest.raises(RuntimeError, match="Publication interrupted"):
                await sync_agent_corpus(db, root)
            assert await snapshot(db) == before

    asyncio.run(scenario())


def test_concurrent_web_startups_do_not_duplicate_material(
    database_dsns, root
):
    async def publish():
        async with publisher(database_dsns) as db:
            return await sync_agent_corpus(db, root, strict=True)

    async def scenario():
        first, second = await asyncio.gather(publish(), publish())
        assert first == second
        async with publisher(database_dsns) as db:
            rows = await snapshot(db)
            assert rows["agent_procedure"]["count"] == 4
            assert rows["agent_prompt"]["count"] == 5

    asyncio.run(scenario())


@pytest.mark.parametrize("environment", ["dev", "qa"])
def test_shared_connections_use_the_application_database(
    database_dsns, monkeypatch, environment
):
    params = conninfo_to_dict(database_dsns["admin"])
    monkeypatch.setitem(
        settings.DATABASES,
        "default",
        {
            "NAME": params["dbname"],
            "USER": params["user"],
            "PASSWORD": params["password"],
            "HOST": params["host"],
            "PORT": params["port"],
        },
    )

    async def scenario():
        connections = DatabaseConnections()
        for lookup in (False, True):
            async with connections.connection(lookup=lookup) as connection:
                row = await (
                    await connection.execute(
                        "SELECT current_database() AS database, current_user AS login"
                    )
                ).fetchone()
                assert row == {
                    "database": params["dbname"],
                    "login": params["user"],
                }
            assert connection.closed

    with override_settings(
        DEPLOYMENT_ENV=environment,
        LP_AGENT_USE_DJANGO_DB=True,
        LP_AGENT_WRITER_DSN="",
        LP_AGENT_LOOKUP_DSN="",
    ):
        asyncio.run(scenario())
