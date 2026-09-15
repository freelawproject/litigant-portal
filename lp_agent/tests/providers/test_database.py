"""
PostgreSQL behavior checks using a temporary database and repository fixtures.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from hashlib import sha256
from importlib.resources import files
from secrets import token_urlsafe
from uuid import uuid4

import pytest
from django.conf import settings
from jsonschema import ValidationError as SchemaValidationError
from psycopg import AsyncConnection, Connection, sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.errors import CheckViolation, InsufficientPrivilege
from psycopg.rows import dict_row, tuple_row
from pydantic import ValidationError

from lp_agent import LPAgent
from lp_agent.adapters.connections import agent_connection, lookup_connection
from lp_agent.adapters.db import (
    AgentDatabase,
    DatabaseConversationStore,
    DatabaseRunStore,
)
from lp_agent.corpus.db_search import get_database_corpus
from lp_agent.errors import AgentAccessError, AgentValidationError
from lp_agent.identity import AgentIdentity
from lp_agent.interfaces import ConversationStore, RunStore
from lp_agent.tests.helpers import (
    RecordingScopeFactory,
    ScriptedModel,
    answer_item,
)
from lp_agent.tools.agent_search import SEARCH_TOOLS, AgentSearch
from lp_agent.types import (
    AccessContext,
    AgentConfiguration,
    AgentSearchQuery,
    AgentSourceQuery,
    CompletedOutcome,
    ModelFinished,
    RunCheckpoint,
    RunRequest,
    RunStatus,
    ScopeSelection,
)
from lp_agent.utils.audit import InstructionArtifact


@pytest.fixture(scope="module")
def database_dsns() -> Iterator[dict[str, str]]:
    """
    Install a temporary database and dedicated writer and lookup login roles.
    """
    config = settings.DATABASES["default"]
    server = make_conninfo(
        host=config["HOST"],
        port=config["PORT"],
        user=config["USER"],
        password=config["PASSWORD"],
        connect_timeout=5,
    )
    name = "test_agent_" + uuid4().hex
    test_dsn = make_conninfo(server, dbname=name)
    dsns = {"admin": test_dsn}
    roles = []
    fixtures = files("litigant_portal").joinpath(
        "app/migrations/agent_sql_0019"
    )
    with Connection.connect(
        server, dbname="postgres", autocommit=True
    ) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name))
        )
        try:
            with Connection.connect(test_dsn) as connection:
                for filename in (
                    "agent_tables.sql",
                    "agent_constraints.sql",
                    "agent_search.sql",
                ):
                    connection.execute((fixtures / filename).read_bytes())
                for permission in ("crud", "lookup"):
                    role = "test_agent_" + permission + "_" + uuid4().hex
                    password = token_urlsafe(32)
                    roles.append(role)
                    connection.execute(
                        sql.SQL(
                            "CREATE ROLE {} LOGIN INHERIT NOSUPERUSER NOCREATEDB "
                            "NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {} IN ROLE {}"
                        ).format(
                            sql.Identifier(role),
                            sql.Literal(password),
                            sql.Identifier("agent_dev_" + permission),
                        )
                    )
                    dsns[permission] = make_conninfo(
                        test_dsn, user=role, password=password
                    )
            yield dsns
        finally:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(name)
                )
            )
            for role in roles:
                admin.execute(
                    sql.SQL("DROP ROLE IF EXISTS {}").format(
                        sql.Identifier(role)
                    )
                )


@pytest.fixture(scope="module")
def dsn(database_dsns: dict[str, str]) -> str:
    """
    Supply only the writer login to ordinary database surface tests.
    """
    return database_dsns["crud"]


@asynccontextmanager
async def database(
    dsn: str, identity: str | None = None
) -> AsyncIterator[AgentDatabase]:
    """
    Use a real connection and commit inside the fixture's temporary database.
    """
    async with agent_connection(dsn) as conn:
        db = AgentDatabase(
            conn, AccessContext(identity_id=identity or uuid4().hex)
        )
        await db.ensure_user()
        yield db


def file_fields(body: str = "Synthetic corpus evidence") -> dict[str, object]:
    """
    Describe an already stored fixture file without performing an S3 operation.
    """
    return {
        "key": uuid4().hex,
        "title": "Fixture document",
        "category": "source",
        "version": 1,
        "s3_bucket": "test-bucket",
        "s3_key": uuid4().hex,
        "sha256": sha256(body.encode()).hexdigest(),
        "byte_size": len(body.encode()),
        "media_type": "text/plain",
        "state": "draft",
    }


async def fixture_scope(
    db: AgentDatabase, *, material: bool = True
) -> dict[str, str]:
    """
    Build one small synthetic court/topic and an owned matter, conversation, run.
    """
    court = await db.save_catalog(
        "court",
        {
            "slug": uuid4().hex,
            "name": "Fixture court",
            "jurisdiction_level": "state",
            "config": {"language": "en"},
        },
    )
    topic = await db.save_catalog(
        "topic", {"slug": uuid4().hex, "title": "Fixture topic"}
    )
    pair = await db.save_catalog(
        "court_topic",
        {
            "court_id": court["id"],
            "topic_id": topic["id"],
            "config": {"language": "es"},
        },
    )
    matter = await db.create_matter(str(pair["id"]), "Fixture matter")
    conversation = await db.create_conversation(
        ScopeSelection(court=court["slug"], topic=topic["slug"])
    )
    await db.bind_matter(str(conversation["id"]), str(matter["id"]))
    run = await db.create_run(
        str(conversation["id"]),
        RunRequest(message="Fixture question"),
        AgentConfiguration(),
        key="request-1",
    )
    ids = {
        "court": court["slug"],
        "topic": topic["slug"],
        "court_id": str(court["id"]),
        "pair": str(pair["id"]),
        "matter": str(matter["id"]),
        "conversation": str(conversation["id"]),
        "run": str(run["id"]),
    }
    if material:
        document = await db.save_document(
            file_fields(), court_id=ids["court_id"]
        )
        await db.replace_document_text(
            str(document["id"]),
            [("Synthetic corpus evidence", {"page": 1})],
            parser_version="fixture",
            chunker_version="fixture",
        )
        await db.save_document(
            {"state": "published"}, record_id=str(document["id"])
        )
        await db.save_catalog(
            "corpus_document",
            {"court_topic_id": pair["id"], "document_id": document["id"]},
        )
        procedure = await db.save_catalog(
            "procedure",
            {
                "court_topic_id": pair["id"],
                "slug": "standard",
                "title": "Fixture procedure",
                "version": 1,
                "guidance": "Synthetic procedure guidance",
            },
        )
        phase = await db.save_catalog(
            "phase",
            {
                "procedure_id": procedure["id"],
                "key": "start",
                "position": 1,
                "title": "Start",
                "instructions": "Synthetic phase instructions",
            },
        )
        definition = await db.save_catalog(
            "fact_definition",
            {
                "key": uuid4().hex,
                "version": 1,
                "scope": "matter",
                "label": "Fixture answer",
                "value_schema": {"type": "boolean"},
            },
        )
        await db.save_catalog(
            "phase_fact",
            {
                "phase_id": phase["id"],
                "fact_definition_id": definition["id"],
                "position": 1,
                "required": True,
            },
        )
        await db.save_catalog(
            "phase_document",
            {
                "phase_id": phase["id"],
                "document_id": document["id"],
                "purpose": "reference",
                "position": 1,
            },
        )
        await db.save_catalog(
            "phase_deadline",
            {
                "phase_id": phase["id"],
                "anchor_fact_definition_id": definition["id"],
                "key": "deadline",
                "label": "Fixture rule",
                "rule": {"days": 5},
            },
        )
        await db.save_catalog(
            "procedure", {"state": "published"}, record_id=str(procedure["id"])
        )
        prompt = await db.save_catalog(
            "prompt",
            {
                "key": uuid4().hex,
                "version": 1,
                "body": "Synthetic prompt fragment",
                "metadata": {"audience": "litigant"},
                "state": "published",
            },
        )
        ids.update(
            document=str(document["id"]),
            procedure=str(procedure["id"]),
            phase=str(phase["id"]),
            definition=str(definition["id"]),
            prompt=str(prompt["id"]),
            prompt_key=prompt["key"],
        )
    return ids


@pytest.mark.postgres
def test_context_pins_revisions_and_honors_withdrawal(dsn: str) -> None:
    async def scenario() -> None:
        async with database(dsn) as db:
            ids = await fixture_scope(db)

            async def load():
                return await get_database_corpus(
                    ids["court"],
                    ids["topic"],
                    db=db,
                    run_id=ids["run"],
                    prompt_keys=[ids["prompt_key"]],
                    prompt_metadata={"audience": "litigant"},
                )

            context = await load()
            assert context.config["settings"] == {"language": "es"}
            assert context.documents[0].content == "Synthetic corpus evidence"
            assert context.prompts[0].body == "Synthetic prompt fragment"
            assert context.document_records[0]["id"] == ids["document"]
            assert len(context.procedures) == 1
            phases = context.procedures[0]["phases"]
            assert isinstance(phases, list) and isinstance(phases[0], dict)
            assert all(
                phases[0][key] for key in ("facts", "documents", "deadlines")
            )
            newer = await db.save_catalog(
                "prompt",
                {
                    "key": ids["prompt_key"],
                    "version": 2,
                    "previous_version_id": ids["prompt"],
                    "body": "New fragment",
                    "metadata": {"audience": "staff"},
                    "state": "published",
                },
            )
            assert (await load()).prompts[0].id == ids["prompt"]
            assert (
                await db.prompt_fragments(
                    [ids["prompt_key"]], {"audience": "litigant"}
                )
                == ()
            )
            assert (await db.prompt_fragments([ids["prompt_key"]]))[
                0
            ].id == str(newer["id"])
            original = await db.document(ids["document"])
            new_document = await db.save_document(
                {
                    **file_fields(),
                    "key": original["key"],
                    "version": 2,
                    "previous_version_id": ids["document"],
                    "state": "published",
                },
                court_id=ids["court_id"],
            )
            await db.replace_document_text(
                str(new_document["id"]),
                [("New document evidence", {})],
                parser_version="fixture",
                chunker_version="fixture",
            )
            new_procedure = await db.save_catalog(
                "procedure",
                {
                    "court_topic_id": ids["pair"],
                    "slug": "standard",
                    "title": "New procedure",
                    "version": 2,
                    "previous_version_id": ids["procedure"],
                    "guidance": "New guidance",
                    "state": "published",
                },
            )
            assert (await load()).manifest == context.manifest
            for table, key in (
                ("prompt", "prompt"),
                ("procedure", "procedure"),
                ("phase", "phase"),
            ):
                with pytest.raises(AgentAccessError):
                    await db.delete_catalog_record(table, ids[key])
            await db.save_catalog(
                "prompt", {"state": "withdrawn"}, record_id=ids["prompt"]
            )
            await db.save_document(
                {"state": "withdrawn"}, record_id=ids["document"]
            )
            await db.save_catalog(
                "procedure", {"state": "withdrawn"}, record_id=ids["procedure"]
            )
            withdrawn = await load()
            assert (
                not withdrawn.prompts
                and not withdrawn.documents
                and not withdrawn.procedures
            )
            assert withdrawn.manifest == context.manifest
            new_run = await db.create_run(
                ids["conversation"],
                RunRequest(message="New run"),
                AgentConfiguration(),
                key="new-run",
            )
            new_context = await get_database_corpus(
                ids["court"],
                ids["topic"],
                db=db,
                run_id=str(new_run["id"]),
                prompt_keys=[ids["prompt_key"]],
            )
            assert new_context.documents[0].source.source_id == str(
                new_document["id"]
            )
            assert new_context.manifest["procedures"][ids["procedure"]] == str(
                new_procedure["id"]
            )
            assert new_context.prompts[0].id == str(newer["id"])

    asyncio.run(scenario())


@pytest.mark.postgres
def test_empty_unknown_and_disabled_scope(dsn: str) -> None:
    async def scenario() -> None:
        async with database(dsn) as db:
            ids = await fixture_scope(db, material=False)
            context = await get_database_corpus(
                ids["court"], ids["topic"], db=db, run_id=ids["run"]
            )
            assert (
                not context.procedures
                and not context.documents
                and not context.prompts
            )
            with pytest.raises(AgentValidationError):
                await get_database_corpus(
                    "another-court", ids["topic"], db=db, run_id=ids["run"]
                )
            await db.save_catalog(
                "court_topic", {"enabled": False}, record_id=ids["pair"]
            )
            with pytest.raises(AgentAccessError):
                await get_database_corpus(
                    ids["court"], ids["topic"], db=db, run_id=ids["run"]
                )

    asyncio.run(scenario())


@pytest.mark.postgres
def test_owned_records_and_store_contracts(dsn: str) -> None:
    async def scenario() -> None:
        async with database(dsn) as db:
            ids = await fixture_scope(db, material=False)
            conversations: ConversationStore = DatabaseConversationStore(
                db.connection
            )
            conversation = await conversations.get(
                access=db.access, conversation_id=ids["conversation"]
            )
            assert conversation.scope == ScopeSelection(
                court=ids["court"], topic=ids["topic"]
            )
            partial = await conversations.create(
                access=db.access, scope=ScopeSelection(court=ids["court"])
            )
            assert partial.scope.topic is None
            other = AgentDatabase(
                db.connection,
                AccessContext(identity_id="other-" + uuid4().hex),
            )
            await other.ensure_user()
            for operation, record_id in (
                (other.conversation, ids["conversation"]),
                (other.run, ids["run"]),
                (other.matter, ids["matter"]),
            ):
                with pytest.raises(AgentAccessError):
                    await operation(record_id)
            private = await other.save_document(
                {**file_fields(), "category": "upload", "state": "private"}
            )
            with pytest.raises(AgentAccessError):
                await db.document(str(private["id"]))
            with pytest.raises(AgentAccessError):
                await db.append_item(
                    ids["conversation"],
                    key="bad-attachment",
                    payload={"text": "hello"},
                    attachment_ids=[str(private["id"])],
                )
            assert await db.conversation_items(ids["conversation"]) == []
            own_file = await db.save_document(
                {**file_fields(), "category": "upload", "state": "private"}
            )
            await db.append_item(
                ids["conversation"],
                key="attachment",
                payload={"text": "hello"},
                attachment_ids=[str(own_file["id"])],
            )
            with pytest.raises(AgentValidationError):
                await db.append_item(
                    ids["conversation"],
                    key="attachment",
                    payload={"text": "hello"},
                )
            with pytest.raises(AgentValidationError):
                await db.save_catalog("user", {"user_id": "bypass"})
            runs: RunStore = DatabaseRunStore(db.connection)
            status = await runs.create(
                access=db.access,
                conversation_id=partial.conversation_id,
                request=RunRequest(message="Hello"),
                configuration=AgentConfiguration(),
            )
            assert status.state == "queued"
            assert (
                await runs.outcome(access=db.access, run_id=status.run_id)
                is None
            )

    asyncio.run(scenario())


@pytest.mark.postgres
def test_message_ordering_retries_and_checkpoint_conflicts(dsn: str) -> None:
    async def scenario() -> None:
        async with database(dsn) as db:
            ids = await fixture_scope(db)
            await db.pin_run_context(
                ids["court"], ids["topic"], run_id=ids["run"]
            )
            procedure = await db.follow_procedure(
                ids["matter"], ids["procedure"]
            )
            initial = RunCheckpoint(
                run_id=ids["run"],
                conversation_id=ids["conversation"],
                data={"step": 0},
            )
            status = RunStatus(
                run_id=ids["run"],
                conversation_id=ids["conversation"],
                state="running",
            )
            saved = await db.commit_checkpoint(initial, status)
            store: RunStore = DatabaseRunStore(db.connection)
            checkpoint = await store.checkpoint(
                access=db.access, run_id=ids["run"]
            )
            assert checkpoint == saved and saved.storage_version == 1

            async def writer(number: int) -> bool:
                async with database(dsn, db.access.identity_id) as writer_db:
                    try:
                        async with writer_db.transaction():
                            await writer_db.append_item(
                                ids["conversation"],
                                key=str(number),
                                payload={"text": str(number)},
                            )
                            step = await writer_db.save_step(
                                ids["run"],
                                key=str(number),
                                kind="check",
                                input={"writer": number},
                            )
                            await writer_db.record_fact(
                                ids["definition"],
                                True,
                                matter_id=ids["matter"],
                            )
                            await writer_db.set_phase_progress(
                                str(procedure["id"]),
                                ids["phase"],
                                str(step["id"]),
                                "active",
                                {"writer": number},
                            )
                            await writer_db.commit_checkpoint(
                                checkpoint.model_copy(
                                    update={"data": {"winner": number}}
                                ),
                                status,
                            )
                        return True
                    except AgentValidationError:
                        return False

            assert sorted(await asyncio.gather(writer(1), writer(2))) == [
                False,
                True,
            ]
            items = await db.conversation_items(ids["conversation"])
            assert len(items) == 1 and items[0]["sequence"] == 1
            assert len(await db.facts(ids["matter"])) == 1
            steps = await (
                await db.connection.execute(
                    "SELECT * FROM public.agent_run_step WHERE run_id = %s",
                    (ids["run"],),
                )
            ).fetchall()
            assert len(steps) == 1
            assert steps[0]["operation_key"] == items[0]["deduplication_key"]
            progress = await (
                await db.connection.execute(
                    "SELECT * FROM public.agent_phase_progress WHERE matter_procedure_id = %s",
                    (procedure["id"],),
                )
            ).fetchall()
            assert len(progress) == 1
            assert progress[0]["last_run_step_id"] == steps[0]["id"]
            repeated = await db.append_item(
                ids["conversation"],
                key=items[0]["deduplication_key"],
                payload=items[0]["payload"],
            )
            assert repeated["id"] == items[0]["id"]
            with pytest.raises(AgentValidationError):
                await db.append_item(
                    ids["conversation"],
                    key=items[0]["deduplication_key"],
                    payload={"changed": True},
                )
            with pytest.raises(AgentValidationError):
                await db.create_run(
                    ids["conversation"],
                    RunRequest(message="Changed"),
                    AgentConfiguration(),
                    key="request-1",
                )
            fresh = await store.checkpoint(access=db.access, run_id=ids["run"])
            assert fresh is not None and fresh.storage_version == 2
            outcome = CompletedOutcome(
                run_id=ids["run"],
                conversation_id=ids["conversation"],
                text="Done",
            )
            await store.commit_checkpoint(
                access=db.access,
                checkpoint=fresh,
                status=RunStatus(
                    run_id=ids["run"],
                    conversation_id=ids["conversation"],
                    state="completed",
                ),
                outcome=outcome,
            )
            assert (
                await store.outcome(access=db.access, run_id=ids["run"])
                == outcome
            )

    asyncio.run(scenario())


@pytest.mark.postgres
def test_document_index_replacement_rolls_back(dsn: str) -> None:
    async def scenario() -> None:
        async with database(dsn) as db:
            ids = await fixture_scope(db)
            original = await db.document(ids["document"])
            with pytest.raises(CheckViolation):
                await db.replace_document_text(
                    ids["document"],
                    [("x" * 70000, {})],
                    parser_version="bad",
                    chunker_version="bad",
                )
            after = await db.document(ids["document"])
            assert after["index_revision"] == original["index_revision"]
            context = await get_database_corpus(
                ids["court"], ids["topic"], db=db, run_id=ids["run"]
            )
            assert context.documents[0].content == "Synthetic corpus evidence"
            await db.replace_document_text(
                ids["document"],
                [],
                parser_version="empty",
                chunker_version="empty",
            )
            after = await db.document(ids["document"])
            assert after["index_revision"] == original["index_revision"] + 1
            empty = await get_database_corpus(
                ids["court"], ids["topic"], db=db, run_id=ids["run"]
            )
            assert not empty.documents and len(empty.document_records) == 1
            assert (
                after["index_state"] == "ready" and after["chunk_count"] == 0
            )

    asyncio.run(scenario())


@pytest.mark.postgres
def test_stored_search_permissions_facts_and_progress(
    dsn: str, database_dsns: dict[str, str]
) -> None:
    async def scenario() -> None:
        async with database(dsn) as db:
            ids = await fixture_scope(db)
            await get_database_corpus(
                ids["court"], ids["topic"], db=db, run_id=ids["run"]
            )
            message = await db.append_item(
                ids["conversation"],
                key="user",
                payload={"role": "user", "content": "Synthetic history"},
                search_text="Synthetic history",
            )
            await db.append_item(
                ids["conversation"],
                key="reasoning",
                payload={"text": "Secret reasoning"},
                kind="reasoning",
                origin="model",
                visibility="internal",
            )
            private = await db.save_document(
                {**file_fields(), "state": "private", "category": "upload"}
            )
            await db.link_document(ids["matter"], str(private["id"]))
            await db.replace_document_text(
                str(private["id"]),
                [("Private document evidence", {})],
                parser_version="fixture",
                chunker_version="fixture",
            )
            with pytest.raises(SchemaValidationError):
                await db.record_fact(
                    ids["definition"], "not a boolean", matter_id=ids["matter"]
                )
            fact = await db.record_fact(
                ids["definition"], True, matter_id=ids["matter"]
            )
            for role in ("basis", "confirmation"):
                await db.fact_evidence(
                    str(fact["id"]),
                    role=role,
                    conversation_item_id=str(message["id"]),
                )
            await db.set_fact_confirmation(str(fact["id"]), "confirmed")
            assert (await db.facts(ids["matter"]))[0]["value"] is True
            personal_definition = await db.save_catalog(
                "fact_definition",
                {
                    "key": uuid4().hex,
                    "version": 1,
                    "scope": "user",
                    "label": "Preferred name",
                    "value_schema": {"type": "string"},
                },
            )
            personal_fact = await db.record_fact(
                str(personal_definition["id"]), "Fixture name"
            )
            await db.fact_evidence(
                str(personal_fact["id"]),
                role="basis",
                conversation_item_id=str(message["id"]),
            )
            instructions = InstructionArtifact(
                instructions="Synthetic instructions"
            )
            step = await db.save_step(
                ids["run"],
                key="model-1",
                kind="model",
                input={"message": "Question"},
                output={"answer": "Fixture"},
                instructions=instructions,
            )
            assert step["instruction_sha256"] == instructions.content_hash()
            procedure = await db.follow_procedure(
                ids["matter"], ids["procedure"]
            )
            await db.set_phase_progress(
                str(procedure["id"]),
                ids["phase"],
                str(step["id"]),
                "active",
                {"reason": "Fixture"},
            )
            async with lookup_connection(database_dsns["lookup"]) as conn:
                search = AgentSearch(
                    conn,
                    access=db.access,
                    run_id=ids["run"],
                    host_policy={},
                )
                for category in (
                    "court_corpus",
                    "user_documents",
                    "user_facts",
                    "matter_facts",
                    "procedure_progress",
                    "conversation_history",
                ):
                    hits = await search.call(
                        "agent_search",
                        json.dumps(
                            {"category": category, "query": "", "limit": 20}
                        ),
                    )
                    assert hits and all(
                        hit["category"] == category for hit in hits
                    )
                    source = await search.call(
                        "agent_get_source",
                        json.dumps(
                            {
                                "category": category,
                                "source_id": hits[0]["source_id"],
                            }
                        ),
                    )
                    assert len(source) == 1
                    assert len(str(source[0]["snippet"])) <= 1000
                    assert "Secret reasoning" not in json.dumps(hits)
                assert (
                    await search.search(
                        AgentSearchQuery(
                            category="court_corpus",
                            query="nonexistentterm",
                            limit=10,
                        )
                    )
                    == ()
                )
                assert await search.search(
                    AgentSearchQuery(
                        category="court_corpus", query="evidence", limit=10
                    )
                )
                await conn.execute("RESET ROLE")
                for role in ("agent_dev_crud", "agent_dev_reader"):
                    with pytest.raises(InsufficientPrivilege):
                        await conn.execute(
                            sql.SQL("SET ROLE {}").format(sql.Identifier(role))
                        )
                with pytest.raises(InsufficientPrivilege):
                    async with conn.transaction():
                        await conn.execute("SELECT * FROM public.agent_prompt")
                with pytest.raises(InsufficientPrivilege):
                    async with conn.transaction():
                        await conn.execute(
                            "SELECT public.agent_lookup_context(%s, %s, '{}')",
                            (db.access.identity_id, ids["run"]),
                        )
                denied = AgentSearch(
                    conn,
                    access=AccessContext(identity_id="wrong-owner"),
                    run_id=ids["run"],
                    host_policy={},
                )
                assert (
                    await denied.search(
                        AgentSearchQuery(
                            category="court_corpus", query="", limit=10
                        )
                    )
                    == ()
                )
                restricted = AgentSearch(
                    conn,
                    access=db.access,
                    run_id=ids["run"],
                    host_policy={"enabled": False},
                )
                assert (
                    await restricted.search(
                        AgentSearchQuery(
                            category="user_documents", query="", limit=10
                        )
                    )
                    == ()
                )

    asyncio.run(scenario())


@pytest.mark.postgres
def test_connection_configuration_and_cleanup(
    dsn: str, database_dsns: dict[str, str]
) -> None:
    async def scenario() -> None:
        for factory, connection_dsn in (
            (agent_connection, dsn),
            (lookup_connection, database_dsns["lookup"]),
        ):
            async with factory(connection_dsn) as conn:
                assert conn.autocommit and conn.row_factory is dict_row
                assert await (
                    await conn.execute("SELECT 1 AS value")
                ).fetchone() == {"value": 1}
            assert conn.closed
            with pytest.raises(RuntimeError, match="Synthetic failure"):
                async with factory(connection_dsn) as conn:
                    raise RuntimeError("Synthetic failure")
            assert conn.closed

        access = AccessContext(identity_id="configuration-test")
        for autocommit, row_factory in ((False, dict_row), (True, tuple_row)):
            async with await AsyncConnection.connect(
                dsn, autocommit=autocommit, row_factory=row_factory
            ) as conn:
                for construct in (
                    lambda: AgentDatabase(conn, access),
                    lambda: DatabaseConversationStore(conn),
                    lambda: DatabaseRunStore(conn),
                    lambda: AgentSearch(
                        conn,
                        access=access,
                        run_id=str(uuid4()),
                        host_policy={},
                    ),
                ):
                    with pytest.raises(AgentValidationError, match="dict_row"):
                        construct()

    asyncio.run(scenario())


@pytest.mark.postgres
def test_lookup_rejects_privileged_logins_and_closes_connections(
    database_dsns: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    opened = []
    connect = AsyncConnection.connect

    async def recording_connect(*args, **kwargs):
        connection = await connect(*args, **kwargs)
        opened.append(connection)
        return connection

    monkeypatch.setattr(AsyncConnection, "connect", recording_connect)

    async def scenario() -> None:
        for connection_dsn in (
            database_dsns["crud"],
            database_dsns["admin"],
            make_conninfo(
                database_dsns["admin"], options="-c role=agent_dev_lookup"
            ),
        ):
            with pytest.raises(AgentValidationError, match="dedicated login"):
                async with lookup_connection(connection_dsn):
                    pytest.fail("Privileged lookup login was accepted")
        assert len(opened) == 3 and all(conn.closed for conn in opened)

    asyncio.run(scenario())


@pytest.mark.postgres
@pytest.mark.parametrize(
    "grant,revoke",
    [
        (
            "GRANT SELECT ON public.agent_prompt TO {}",
            "REVOKE SELECT ON public.agent_prompt FROM {}",
        ),
        (
            "GRANT EXECUTE ON FUNCTION public.agent_lookup_context(text, uuid, jsonb) TO {}",
            "REVOKE EXECUTE ON FUNCTION public.agent_lookup_context(text, uuid, jsonb) FROM {}",
        ),
        (
            "GRANT agent_dev_crud TO {} WITH INHERIT FALSE",
            "REVOKE agent_dev_crud FROM {}",
        ),
    ],
)
def test_lookup_rejects_extra_privileges(
    database_dsns: dict[str, str], grant: str, revoke: str
) -> None:
    login = sql.Identifier(conninfo_to_dict(database_dsns["lookup"])["user"])

    async def scenario() -> None:
        with pytest.raises(AgentValidationError, match="dedicated login"):
            async with lookup_connection(database_dsns["lookup"]):
                pytest.fail("Extra lookup privileges were accepted")

    with Connection.connect(database_dsns["admin"], autocommit=True) as admin:
        admin.execute(sql.SQL(grant).format(login))
        try:
            asyncio.run(scenario())
        finally:
            admin.execute(sql.SQL(revoke).format(login))


@pytest.mark.postgres
@pytest.mark.parametrize("terminal", ["completed", "failed", "cancelled"])
def test_database_stores_persist_terminal_outcomes(
    dsn: str, terminal: str
) -> None:
    async def scenario() -> None:
        async with database(dsn) as db:
            ids = await fixture_scope(db, material=False)
            model = ScriptedModel(
                [RuntimeError("Synthetic model failure")]
                if terminal == "failed"
                else [answer_item("Done"), ModelFinished(reason="stop")]
            )
            environment = AgentIdentity(
                access=db.access,
                scope=ScopeSelection(court=ids["court"], topic=ids["topic"]),
                conversations=DatabaseConversationStore(db.connection),
                runs=DatabaseRunStore(db.connection),
                scope_factory=RecordingScopeFactory(model),
            )
            async with LPAgent(environment=environment) as agent:
                run = await agent.run(message="Synthetic question")
                if terminal == "cancelled":
                    await run.cancel()
                outcome = await run.result()
                assert outcome.state == terminal
                assert (await run.status()).state == terminal
                events = [event async for event in run.events()]
                assert events[-1].payload.outcome == outcome
            assert (
                await environment.runs.outcome(
                    access=db.access, run_id=run.run_id
                )
                == outcome
            )
            checkpoint = await environment.runs.checkpoint(
                access=db.access, run_id=run.run_id
            )
            assert checkpoint is not None and checkpoint.storage_version == 2

    asyncio.run(scenario())


def test_tool_arguments_are_closed_and_memory_is_excluded() -> None:
    assert {tool.name for tool in SEARCH_TOOLS} == {
        "agent_search",
        "agent_get_source",
    }
    for values in (
        {"category": "memory", "query": "", "limit": 10},
        {"category": "court_corpus", "query": "", "limit": 21},
        {
            "category": "court_corpus",
            "query": "",
            "limit": 10,
            "user_id": "spoof",
        },
    ):
        with pytest.raises(ValidationError):
            AgentSearchQuery.model_validate(values)
    with pytest.raises(ValidationError):
        AgentSourceQuery.model_validate(
            {"category": "prompt", "source_id": uuid4().hex}
        )
