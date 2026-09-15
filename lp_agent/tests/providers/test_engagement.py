"""
Real database turns, conversation selection, atomic tool effects, and caller boundaries.
"""

import asyncio
import inspect
import json
from collections.abc import AsyncGenerator, Iterator
from contextlib import asynccontextmanager
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.conf import settings
from django.test import override_settings
from psycopg import AsyncConnection
from psycopg.rows import DictRow
from pydantic import JsonValue

from lp_agent import LPAgent
from lp_agent.adapters.bedrock import MODEL_CHOICES, BedrockClient
from lp_agent.adapters.db import DatabaseRunStore
from lp_agent.adapters.environment import ModelScopeFactory, create_environment
from lp_agent.adapters.preparation import DatabasePreparationSession
from lp_agent.adapters.session import (
    DatabaseConnections,
    DatabasePreparationService,
    LazyConversationStore,
    LazyRunStore,
)
from lp_agent.errors import (
    AgentAccessError,
    AgentStorageError,
    AgentValidationError,
)
from lp_agent.identity import AgentIdentity
from lp_agent.interfaces import ModelClient
from lp_agent.tests.fixtures.preparation import load_preparation_fixture
from lp_agent.tests.helpers import PassingJudge
from lp_agent.tests.providers.test_database import database, fixture_scope
from lp_agent.tests.providers.test_database import (
    database_dsns as database_dsns,  # noqa: F401
)
from lp_agent.types import (
    AccessContext,
    ModelEvent,
    ModelFinished,
    ModelItem,
    ModelMessage,
    ModelOutputItem,
    ModelRequest,
    RunCheckpoint,
    ScopeSelection,
    ToolCall,
)

pytestmark = pytest.mark.postgres


@pytest.fixture(name="dsn", scope="module")
def preparation_database(database_dsns: dict[str, str]) -> Iterator[str]:  # noqa: F811
    async def seed(value: str) -> None:
        async with database(value) as db:
            await load_preparation_fixture(db, settings.BASE_DIR)

    with override_settings(
        LP_AGENT_WRITER_DSN=database_dsns["crud"],
        LP_AGENT_LOOKUP_DSN=database_dsns["lookup"],
        CORPUS_COURT=None,
    ):
        asyncio.run(seed(database_dsns["crud"]))
        yield database_dsns["crud"]


class Turns:
    """
    Emit controlled responses and retain the complete native model context.
    """

    def __init__(self, *responses: str | list[ModelItem]) -> None:
        self.responses = iter(responses)
        self.requests: list[ModelRequest] = []

    async def stream(
        self, request: ModelRequest
    ) -> AsyncGenerator[ModelEvent]:
        self.requests.append(request)
        response = next(self.responses)
        items = (
            [ModelMessage(role="assistant", content=response)]
            if isinstance(response, str)
            else response
        )
        for item in items:
            yield ModelOutputItem(item=item)
        yield ModelFinished(
            reason="tool_calls"
            if any(isinstance(item, ToolCall) for item in items)
            else "stop"
        )


def call(name: str, **arguments: JsonValue) -> ToolCall:
    return ToolCall(
        call_id=uuid4().hex, name=name, arguments=json.dumps(arguments)
    )


def select(slug: str) -> ToolCall:
    return call("select_procedure", slug=slug, evidence=f"Prepare {slug}")


class TrackedConnections(DatabaseConnections):
    def __init__(self, dsn: str) -> None:
        super().__init__(
            lambda: {"writer": dsn, "lookup": settings.LP_AGENT_LOOKUP_DSN}
        )
        self.opened: list[AsyncConnection[DictRow]] = []

    @asynccontextmanager
    async def connection(self, *, lookup: bool = False):
        async with super().connection(lookup=lookup) as connection:
            self.opened.append(connection)
            yield connection


def environment(
    dsn: str,
    model: ModelClient,
    identity: str,
    court: str | None = "franklin-county-oh",
    topic: str | None = "eviction",
    *,
    connections: DatabaseConnections | None = None,
    model_identifier: str = MODEL_CHOICES[0][0],
    judge: ModelClient | None = None,
) -> AgentIdentity:
    access = AccessContext(identity_id=identity)
    connections = connections or DatabaseConnections(
        lambda: {"writer": dsn, "lookup": settings.LP_AGENT_LOOKUP_DSN}
    )
    return AgentIdentity(
        access=access,
        scope=ScopeSelection(court=court, topic=topic),
        conversations=LazyConversationStore(connections),
        runs=LazyRunStore(connections),
        preparation=DatabasePreparationService(
            connections, access, model_identifier
        ),
        scope_factory=ModelScopeFactory(
            access,
            model,
            judge or PassingJudge(),
            settings.BASE_DIR,
        ),
    )


async def turn(
    env: AgentIdentity, message: str, conversation_id: str | None = None
) -> RunCheckpoint:
    async with LPAgent(environment=env) as agent:
        run = await agent.run(message=message, conversation_id=conversation_id)
        outcome = await run.result()
        assert outcome.state == "completed", outcome
        checkpoint = await env.runs.checkpoint(
            access=env.access, run_id=run.run_id
        )
        assert checkpoint is not None
        return checkpoint


@pytest.mark.parametrize(
    ("court", "topic", "evidence"),
    [
        ("north-dakota", "adult-name-change", "$160"),
        ("franklin-county-oh", "eviction", "28 days"),
    ],
)
def test_grounded_question_without_procedure_and_durable_owned_followup(
    dsn: str, court: str, topic: str, evidence: str
) -> None:
    async def scenario() -> None:
        identity = uuid4().hex
        model = Turns("First answer")
        saved = await turn(
            environment(dsn, model, identity, court, topic),
            "What is the procedure?",
        )
        assert saved.data["progress"]["procedure"] is None
        assert evidence in model.requests[0].instructions
        assert {tool.name for tool in model.requests[0].tools} == {
            "select_procedure",
            "agent_search",
            "agent_get_source",
        }
        model = Turns("Follow-up answer")
        await turn(
            environment(dsn, model, identity, court, topic),
            "What next?",
            saved.conversation_id,
        )
        assert any(
            isinstance(item, ModelMessage) and item.content == "First answer"
            for item in model.requests[0].input
        )
        async with LPAgent(
            environment=environment(dsn, Turns(), uuid4().hex, court, topic)
        ) as agent:
            with pytest.raises(AgentAccessError):
                await agent.run(
                    message="Read it", conversation_id=saved.conversation_id
                )
        async with database(dsn, identity) as db:
            rows = await (
                await db.connection.execute(
                    "SELECT output FROM agent_run_step WHERE run_id = %s AND kind = 'judge'",
                    (saved.run_id,),
                )
            ).fetchall()
            assert rows[0]["output"]["status"] == "approved"

    asyncio.run(scenario())


def test_conversation_selects_procedure_only_with_current_message_evidence(
    dsn: str,
) -> None:
    async def scenario() -> None:
        identity = uuid4().hex
        model = Turns("Do you rent the property, or are you the landlord?")
        saved = await turn(
            environment(dsn, model, identity), "Help me prepare for eviction."
        )
        assert saved.data["progress"]["procedure"] is None
        model = Turns(
            [
                call(
                    "select_procedure", slug="tenant", evidence="I am a tenant"
                )
            ],
            "Please clarify.",
        )
        saved = await turn(
            environment(dsn, model, identity), "Help", saved.conversation_id
        )
        assert saved.data["progress"]["procedure"] is None
        assert "current user message" in model.requests[-1].input[-1].output
        model = Turns(
            [select("not-a-procedure")], "Please choose a supported procedure."
        )
        saved = await turn(
            environment(dsn, model, identity),
            "Prepare not-a-procedure",
            saved.conversation_id,
        )
        assert saved.data["progress"]["procedure"] is None
        saved = await turn(
            environment(
                dsn, Turns([select("tenant")], "Let's prepare."), identity
            ),
            "Prepare tenant",
            saved.conversation_id,
        )
        assert saved.data["progress"]["procedure"] == "tenant"

    asyncio.run(scenario())


def test_fact_evidence_corrections_confirmation_and_reopened_review(
    dsn: str,
) -> None:
    async def scenario() -> None:
        identity = uuid4().hex
        saved = await turn(
            environment(
                dsn,
                Turns([select("tenant")], "When did you receive the papers?"),
                identity,
            ),
            "Prepare tenant",
        )
        for value in ("2026-10-01", "2026-10-02"):
            model = Turns(
                [
                    call(
                        "record_facts",
                        facts=[
                            {
                                "key": "eviction_papers_received_date",
                                "value": value,
                                "evidence": value,
                            }
                        ],
                    )
                ],
                "Please review the date.",
            )
            saved = await turn(
                environment(dsn, model, identity),
                f"Received on {value}.",
                saved.conversation_id,
            )
        for phase in ("your-key-dates", "review"):
            saved = await turn(
                environment(
                    dsn,
                    Turns(
                        [
                            call(
                                "acknowledge_phase",
                                phase_key=phase,
                                evidence="Yes, correct.",
                            )
                        ],
                        "Preparation updated.",
                    ),
                    identity,
                ),
                "Yes, correct.",
                saved.conversation_id,
            )
        assert saved.data["progress"]["complete"]
        assert (
            saved.data["progress"]["facts"]["eviction_papers_received_date"]
            == "2026-10-02"
        )
        async with database(dsn, identity) as db:
            rows = await (
                await db.connection.execute(
                    "SELECT state, confirmation_state FROM agent_fact_assertion WHERE user_id = %s ORDER BY observed_at",
                    (identity,),
                )
            ).fetchall()
            assert rows == [
                {"state": "superseded", "confirmation_state": "unconfirmed"},
                {"state": "active", "confirmation_state": "confirmed"},
            ]
            evidence = await (
                await db.connection.execute(
                    "SELECT e.role, i.origin, i.conversation_id FROM agent_fact_evidence e JOIN agent_fact_assertion f ON f.id = e.fact_assertion_id JOIN agent_conversation_item i ON i.id = e.conversation_item_id WHERE f.user_id = %s",
                    (identity,),
                )
            ).fetchall()
            assert {row["role"] for row in evidence} == {
                "basis",
                "confirmation",
            }
            assert all(
                row["origin"] == "user"
                and str(row["conversation_id"]) == saved.conversation_id
                for row in evidence
            )
        saved = await turn(
            environment(
                dsn,
                Turns(
                    [
                        call(
                            "record_facts",
                            facts=[
                                {
                                    "key": "eviction_papers_received_date",
                                    "value": "2026-10-03",
                                    "evidence": "2026-10-03",
                                }
                            ],
                        )
                    ],
                    "Please confirm the corrected summary.",
                ),
                identity,
            ),
            "Correction: 2026-10-03",
            saved.conversation_id,
        )
        assert not saved.data["progress"]["complete"]
        assert saved.data["progress"]["current_phase"]["key"] == "review"
        other = await turn(
            environment(
                dsn,
                Turns([select("tenant")], "What are your dates?"),
                identity,
            ),
            "Prepare tenant",
        )
        assert other.data["progress"]["facts"] == {}

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("value", "quote"),
    [
        ("2026-02-31", "2026-02-31"),
        (True, "2026-02-31"),
        ("2026-02-28", "not in the message"),
    ],
)
def test_invalid_fact_is_a_tool_error_without_partial_writes(
    dsn: str, value: JsonValue, quote: str
) -> None:
    async def scenario() -> None:
        identity = uuid4().hex
        saved = await turn(
            environment(dsn, Turns([select("tenant")], "Dates?"), identity),
            "Prepare tenant",
        )
        model = Turns(
            [
                call(
                    "record_facts",
                    facts=[
                        {
                            "key": "eviction_papers_received_date",
                            "value": "2026-10-01",
                            "evidence": "2026-10-01",
                        },
                        {
                            "key": "eviction_hearing_date",
                            "value": value,
                            "evidence": quote,
                        },
                    ],
                )
            ],
            "Please check that date.",
        )
        saved = await turn(
            environment(dsn, model, identity),
            "2026-10-01 and 2026-02-31",
            saved.conversation_id,
        )
        assert saved.data["progress"]["facts"] == {}
        assert '"error"' in model.requests[-1].input[-1].output

    asyncio.run(scenario())


def test_acknowledgement_requires_a_separate_unchanged_reply(dsn: str) -> None:
    async def scenario() -> None:
        identity = uuid4().hex
        model = Turns(
            [
                select("tenant"),
                call(
                    "acknowledge_phase",
                    phase_key="your-key-dates",
                    evidence="Yes",
                ),
            ],
            "Please review the current step.",
        )
        saved = await turn(
            environment(dsn, model, identity), "Prepare tenant. Yes"
        )
        assert "not available" in model.requests[-1].input[-1].output
        cases = [
            (
                "No, I am not ready.",
                [
                    call(
                        "acknowledge_phase",
                        phase_key="your-key-dates",
                        evidence="ready",
                    )
                ],
                "your-key-dates",
                "does not explicitly acknowledge",
            ),
            (
                "Yes, continue.",
                [
                    call(
                        "acknowledge_phase",
                        phase_key="your-key-dates",
                        evidence="Yes",
                    ),
                    call(
                        "acknowledge_phase", phase_key="review", evidence="Yes"
                    ),
                ],
                "review",
                "separate reply",
            ),
            (
                "Correct to 2026-10-02. Yes, correct.",
                [
                    call(
                        "record_facts",
                        facts=[
                            {
                                "key": "eviction_papers_received_date",
                                "value": "2026-10-02",
                                "evidence": "2026-10-02",
                            }
                        ],
                    ),
                    call(
                        "acknowledge_phase", phase_key="review", evidence="Yes"
                    ),
                ],
                "review",
                "separate reply",
            ),
        ]
        for message, calls, phase, error in cases:
            model = Turns(calls, "Please review the current step.")
            saved = await turn(
                environment(dsn, model, identity),
                message,
                saved.conversation_id,
            )
            assert saved.data["progress"]["current_phase"]["key"] == phase
            assert not saved.data["progress"]["complete"]
            assert error in model.requests[-1].input[-1].output
        assert "acknowledge_phase" not in {
            tool.name for tool in model.requests[-1].tools
        }

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("court", "topic", "procedure"),
    [
        ("north-dakota", "adult-name-change", "standard"),
        ("north-dakota", "adult-name-change", "waiver"),
        ("franklin-county-oh", "eviction", "tenant"),
        ("franklin-county-oh", "eviction", "landlord"),
    ],
)
def test_all_four_preparation_handoffs(
    dsn: str, court: str, topic: str, procedure: str
) -> None:
    async def scenario() -> None:
        identity = uuid4().hex

        def env(model: ModelClient) -> AgentIdentity:
            return environment(dsn, model, identity, court, topic)

        saved = await turn(
            env(Turns([select(procedure)], "Let's prepare.")),
            f"Prepare {procedure}",
        )
        async with database(dsn, identity) as db:
            definitions = await (
                await db.connection.execute(
                    "SELECT DISTINCT fd.* FROM agent_fact_definition fd JOIN agent_phase_fact pf ON pf.fact_definition_id = fd.id JOIN agent_phase ph ON ph.id = pf.phase_id JOIN agent_procedure p ON p.id = ph.procedure_id JOIN agent_court_topic ct ON ct.id = p.court_topic_id JOIN agent_court c ON c.id = ct.court_id WHERE c.slug = %s AND p.slug = %s",
                    (court, procedure),
                )
            ).fetchall()
        facts = []
        for definition in definitions:
            schema = definition["value_schema"]
            value = schema.get("enum", [None])[0]
            if value is None:
                value = {
                    "string": "Demo value",
                    "number": 0,
                    "boolean": False,
                }[schema["type"]]
            if schema.get("format") == "date":
                value = "2026-10-01"
            if definition["key"] == "name_change_fee_waiver_needed":
                value = True
            facts.append(
                {
                    "key": definition["key"],
                    "value": value,
                    "evidence": json.dumps(value),
                }
            )
        message = "Fictional demo facts: " + json.dumps(
            {fact["key"]: fact["value"] for fact in facts}
        )
        saved = await turn(
            env(
                Turns(
                    [call("record_facts", facts=facts)],
                    "Saved. Please review.",
                )
            ),
            message,
            saved.conversation_id,
        )
        for _ in range(10):
            progress = saved.data["progress"]
            if progress["complete"]:
                break
            phase = progress["current_phase"]
            assert phase["missing"] == []
            saved = await turn(
                env(
                    Turns(
                        [
                            call(
                                "acknowledge_phase",
                                phase_key=phase["key"],
                                evidence="Yes, confirmed.",
                            )
                        ],
                        "Preparation updated.",
                    )
                ),
                "Yes, confirmed.",
                saved.conversation_id,
            )
        assert saved.data["progress"]["complete"]
        assert saved.data["progress"]["resources"]
        packet = saved.data["progress"]["packet"]
        assert (
            ("nd-fee-waiver-petition" in packet)
            if topic == "adult-name-change"
            else packet == []
        )

    asyncio.run(scenario())


def test_real_search_failed_history_and_native_reasoning_continuation(
    dsn: str,
) -> None:
    from lp_agent.types import ReasoningItem

    async def scenario() -> None:
        identity = uuid4().hex
        model = Turns(
            [
                call(
                    "agent_search",
                    category="court_corpus",
                    query="notice",
                    limit=3,
                )
            ],
            *["Bad citation [source:unavailable]."] * 3,
        )
        async with LPAgent(
            environment=environment(dsn, model, identity)
        ) as agent:
            run = await agent.run(message="What is a notice?")
            assert (await run.result()).error.code == "response_rejected"
        result = json.loads(model.requests[1].input[-1].output)
        assert result and all(
            row["category"] == "court_corpus" for row in result
        )
        reasoning = ReasoningItem(
            id="reasoning-1",
            encrypted_content="signed opaque continuation",
            summary=(),
        )
        model = Turns(
            [reasoning, ModelMessage(role="assistant", content="Retry answer")]
        )
        saved = await turn(
            environment(dsn, model, identity),
            "Try again.",
            run.conversation_id,
        )
        assert not any(
            isinstance(item, ToolCall) for item in model.requests[0].input
        )
        assert not any(
            isinstance(item, ModelMessage)
            and "Bad citation" in str(item.content)
            for item in model.requests[0].input
        )
        model = Turns("Follow-up")
        await turn(
            environment(dsn, model, identity),
            "And next?",
            saved.conversation_id,
        )
        assert reasoning in model.requests[0].input

    asyncio.run(scenario())


def test_active_conversation_cancellation_and_connection_cleanup(
    dsn: str,
) -> None:
    class WaitingModel:
        def __init__(self) -> None:
            self.entered = asyncio.Event()

        async def stream(
            self, request: ModelRequest
        ) -> AsyncGenerator[ModelEvent]:
            self.entered.set()
            await asyncio.Event().wait()
            yield ModelFinished(reason="stop")

    async def scenario() -> None:
        identity = uuid4().hex
        model = WaitingModel()
        connections = TrackedConnections(dsn)
        async with LPAgent(
            environment=environment(
                dsn, model, identity, connections=connections
            )
        ) as first:
            run = await first.run(message="Help me prepare.")
            await asyncio.wait_for(model.entered.wait(), 5)
            async with LPAgent(
                environment=environment(
                    dsn, Turns(), identity, connections=connections
                )
            ) as second:
                with pytest.raises(
                    AgentValidationError, match="active response"
                ):
                    await second.run(
                        message="Another request",
                        conversation_id=run.conversation_id,
                    )
            assert (await run.status()).state == "running"
            await run.cancel()
            assert (await run.result()).state == "cancelled"
            assert (await run.status()).state == "cancelled"
        assert all(connection.closed for connection in connections.opened)
        await turn(
            environment(dsn, Turns("Resumed"), identity),
            "Continue",
            run.conversation_id,
        )

    asyncio.run(scenario())


def test_same_agent_runs_use_independent_transactions(dsn: str) -> None:
    async def scenario() -> None:
        entered, release = asyncio.Event(), asyncio.Event()
        original = DatabasePreparationSession.save_progress

        async def paused(self, *args, **kwargs):
            await original(self, *args, **kwargs)
            entered.set()
            await release.wait()

        connections = TrackedConnections(dsn)
        model = Turns(
            [select("tenant")], "Second independent answer", "First finished"
        )
        env = environment(dsn, model, uuid4().hex, connections=connections)
        with patch.object(DatabasePreparationSession, "save_progress", paused):
            async with LPAgent(environment=env) as agent:
                first = await agent.run(message="Prepare tenant")
                await asyncio.wait_for(entered.wait(), 5)
                second = await agent.run(message="General question")
                assert (
                    await asyncio.wait_for(second.result(), 5)
                ).state == "completed"
                assert first.conversation_id != second.conversation_id
                release.set()
                assert (await first.result()).state == "completed"
        assert all(connection.closed for connection in connections.opened)

    asyncio.run(scenario())


def test_tool_checkpoint_failure_rolls_back_effects_and_closes_connections(
    dsn: str,
) -> None:
    async def scenario() -> None:
        identity = uuid4().hex
        saved = await turn(
            environment(dsn, Turns([select("tenant")], "Dates?"), identity),
            "Prepare tenant",
        )
        connections = TrackedConnections(dsn)
        model = Turns(
            [
                call(
                    "record_facts",
                    facts=[
                        {
                            "key": "eviction_papers_received_date",
                            "value": "2026-10-01",
                            "evidence": "2026-10-01",
                        }
                    ],
                )
            ]
        )
        original = DatabaseRunStore.commit_checkpoint

        async def fail(self, *, checkpoint, **kwargs):
            if checkpoint.data["progress"]["facts"]:
                raise RuntimeError("Private storage diagnostics")
            return await original(self, checkpoint=checkpoint, **kwargs)

        env = environment(dsn, model, identity, connections=connections)
        agent = LPAgent(environment=env)
        with patch.object(DatabaseRunStore, "commit_checkpoint", fail):
            run = await agent.run(
                message="2026-10-01", conversation_id=saved.conversation_id
            )
            with pytest.raises(AgentStorageError):
                await run.result()
            with pytest.raises(AgentStorageError):
                await agent.aclose()
        assert all(connection.closed for connection in connections.opened)
        async with database(dsn, identity) as db:
            assert await db.facts() == []
            row = await (
                await db.connection.execute(
                    "SELECT count(*) AS count FROM agent_fact_assertion WHERE user_id = %s",
                    (identity,),
                )
            ).fetchone()
            assert row["count"] == 0
            row = await db.run(run.run_id)
            assert row["outcome"] is None

    asyncio.run(scenario())


def test_missing_scope_and_changed_model_do_not_leave_orphan_runs(
    dsn: str,
) -> None:
    async def scenario() -> None:
        identity = uuid4().hex
        model = Turns()
        async with LPAgent(
            environment=environment(dsn, model, identity, court=None)
        ) as agent:
            run = await agent.run(message="Hello")
            assert "Choose the court" in (await run.result()).text
        assert model.requests == []
        saved = await turn(environment(dsn, Turns("Answer"), identity), "Help")
        async with LPAgent(
            environment=environment(
                dsn, Turns(), identity, model_identifier="changed-model"
            )
        ) as agent:
            with pytest.raises(AgentValidationError, match="model changed"):
                await agent.run(
                    message="Continue", conversation_id=saved.conversation_id
                )
        async with LPAgent(
            environment=environment(
                dsn, Turns(), identity, court="unavailable"
            )
        ) as agent:
            with pytest.raises(AgentAccessError):
                await agent.run(message="Help")
        async with database(dsn, identity) as db:
            row = await (
                await db.connection.execute(
                    "SELECT count(*) AS count FROM agent_run r JOIN agent_conversation c ON c.id = r.conversation_id WHERE c.user_id = %s",
                    (identity,),
                )
            ).fetchone()
            assert row["count"] == 2

    asyncio.run(scenario())


@pytest.mark.django_db
@override_settings(BEDROCK_API_KEY="test-only-key")
def test_unchanged_portal_agent_call_uses_package_database_services(
    dsn: str,
) -> None:
    from django.db.backends.postgresql.base import DatabaseWrapper

    from litigant_portal.agent import PortalAgent
    from litigant_portal.app.models import UserIdentity

    identity = UserIdentity.objects.create(session_key="package-contract-test")
    model = Turns("Grounded answer through the original caller")
    assert tuple(inspect.signature(create_environment).parameters) == (
        "identity_id",
        "model",
        "api_key",
        "resource_root",
        "judge",
        "court",
        "topic",
    )
    assert tuple(inspect.signature(PortalAgent).parameters) == (
        "identity",
        "model",
        "judge",
        "court",
        "topic",
        "runtime",
        "interrupt_behavior",
        "limits",
    )
    assert tuple(AgentIdentity.__dataclass_fields__) == (
        "access",
        "conversations",
        "runs",
        "scope_factory",
        "scope",
        "preparation",
    )
    # Exercise the real factory, lazy configuration reader, and async connection.
    # Opening a synchronous Django connection during the run must fail this test.
    with (
        patch.object(
            DatabaseWrapper,
            "get_connection_params",
            return_value={
                "conninfo": dsn,
                "cursor_factory": object(),
                "context": object(),
            },
        ),
        patch.object(
            DatabaseWrapper,
            "get_new_connection",
            side_effect=AssertionError("Synchronous ORM connection used"),
        ),
        patch.object(
            BedrockClient,
            "stream",
            lambda self, request: (
                Turns('{"approved": true, "findings": []}')
                if request.instructions.startswith("You review candidate")
                else model
            ).stream(request),
        ),
    ):
        agent = PortalAgent(
            identity=identity,
            model=MODEL_CHOICES[0][0],
            court="north-dakota",
            topic="adult-name-change",
            runtime="Direct",
        )

        async def scenario() -> None:
            async with agent:
                run = await agent.run(message="What is the filing fee?")
                assert (await run.result()).state == "completed"
                checkpoint = await agent.environment.runs.checkpoint(
                    access=agent.environment.access, run_id=run.run_id
                )
                assert checkpoint.data["progress"]["procedure"] is None

        asyncio.run(scenario())
    assert "$160" in model.requests[0].instructions


@pytest.mark.parametrize("material", [False, True])
def test_empty_corpus_or_missing_prompts_do_not_create_a_run(
    dsn: str, material: bool
) -> None:
    async def scenario() -> None:
        async with database(dsn) as db:
            scope = await fixture_scope(db, material=material)
        identity = uuid4().hex
        model = Turns()
        async with LPAgent(
            environment=environment(
                dsn, model, identity, scope["court"], scope["topic"]
            )
        ) as agent:
            if material:
                with pytest.raises(
                    AgentValidationError, match="prompt material"
                ):
                    await agent.run(message="Help")
            else:
                run = await agent.run(message="Help")
                assert (
                    "don’t have published material"
                    in (await run.result()).text
                )
        assert model.requests == []
        async with database(dsn, identity) as db:
            row = await (
                await db.connection.execute(
                    "SELECT count(*) AS count FROM agent_conversation WHERE user_id = %s",
                    (identity,),
                )
            ).fetchone()
            assert row["count"] == (0 if material else 1)

    asyncio.run(scenario())


def test_supplied_form_excerpt_is_a_valid_citation(dsn: str) -> None:
    async def scenario() -> None:
        model = Turns(
            "Prepare the Petition for Name Change. [source:nd-name-change-petition]"
        )
        env = environment(
            dsn, model, uuid4().hex, "north-dakota", "adult-name-change"
        )
        async with LPAgent(environment=env) as agent:
            run = await agent.run(message="Which form is the petition?")
            outcome = await run.result()
            assert outcome.state == "completed"
            assert outcome.sources[0].source_id == "nd-name-change-petition"
            assert outcome.sources[0].locator.startswith(
                "https://www.ndcourts.gov/"
            )
        assert "sources" in model.requests[0].instructions

    asyncio.run(scenario())


def test_unavailable_acknowledgement_evidence_reopens_the_phase(
    dsn: str,
) -> None:
    async def scenario() -> None:
        identity = uuid4().hex
        saved = await turn(
            environment(dsn, Turns([select("tenant")], "Dates?"), identity),
            "Prepare tenant",
        )
        saved = await turn(
            environment(
                dsn,
                Turns(
                    [
                        call(
                            "acknowledge_phase",
                            phase_key="your-key-dates",
                            evidence="Yes, continue.",
                        )
                    ],
                    "Please review the final summary.",
                ),
                identity,
            ),
            "Yes, continue.",
            saved.conversation_id,
        )
        assert saved.data["progress"]["current_phase"]["key"] == "review"
        async with database(dsn, identity) as db:
            await db.connection.execute(
                "UPDATE agent_conversation_item SET context_state = 'superseded' WHERE run_id = %s AND origin = 'user'",
                (saved.run_id,),
            )
        saved = await turn(
            environment(dsn, Turns("Please review the dates step."), identity),
            "What next?",
            saved.conversation_id,
        )
        assert (
            saved.data["progress"]["current_phase"]["key"] == "your-key-dates"
        )
        assert not saved.data["progress"]["complete"]

    asyncio.run(scenario())


@pytest.mark.parametrize("reject_count", [1, 2, 3])
def test_judge_corrections_are_private_and_do_not_repeat_tools(
    dsn, reject_count
):
    from lp_agent.adapters.conversations import conversation_snapshot
    from lp_agent.types import ReasoningItem, TextEvent

    async def scenario():
        identity = uuid4().hex
        rejected = json.dumps(
            {
                "approved": False,
                "findings": [
                    {
                        "code": "state_mismatch",
                        "message": "Describe preparation only; nothing was filed.",
                    }
                ],
            }
        )
        approved = '{"approved": true, "findings": []}'
        judge = Turns(*([rejected] * reject_count), approved)
        drafts = [
            f"Rejected draft {i}: I filed your case."
            for i in range(reject_count)
        ]
        model = Turns(
            [select("tenant")],
            *[
                [
                    ReasoningItem(
                        id=f"rejected-reasoning-{index}",
                        encrypted_content="private rejected reasoning",
                        summary=(),
                    ),
                    ModelMessage(role="assistant", content=draft),
                ]
                for index, draft in enumerate(drafts)
            ],
            "Preparation selected. What date did you receive the papers?",
        )
        env = environment(dsn, model, identity, judge=judge)
        async with LPAgent(environment=env) as agent:
            run = await agent.run(message="Prepare tenant")
            events = [event async for event in run.events()]
            outcome = await run.result()
        assert len(judge.requests) == min(reject_count + 1, 3)
        assert all(request.tools == () for request in model.requests[2:])
        for index, request in enumerate(judge.requests):
            reviewed = json.loads(request.input[0].content)
            assert (
                "private rejected reasoning" not in request.model_dump_json()
            )
            assert reviewed["previous_reviews"] == [
                {
                    "candidate": draft,
                    "findings": json.loads(rejected)["findings"],
                }
                for draft in drafts[:index]
            ]
        for index, request in enumerate(model.requests[2:], start=1):
            assert (
                "private rejected reasoning" not in request.model_dump_json()
            )
            correction = request.input[-1]
            assert isinstance(correction, ModelMessage)
            assert correction.role == "developer"
            assert all(draft in correction.content for draft in drafts[:index])
            assert "Describe preparation only" in correction.content
            assert not any(
                isinstance(item, ModelMessage)
                and item.role == "assistant"
                and item.content in drafts
                for item in request.input
            )
        text = "".join(
            event.payload.delta
            for event in events
            if isinstance(event.payload, TextEvent)
        )
        assert not any(draft in text for draft in drafts)
        assert outcome.state == (
            "failed" if reject_count == 3 else "completed"
        )
        if reject_count == 3:
            assert outcome.error.code == "response_rejected"
            assert text == ""
        else:
            assert text == outcome.text
        snapshot = await conversation_snapshot(env.access, run.conversation_id)
        assert not any(draft in json.dumps(snapshot) for draft in drafts)
        assert "private rejected reasoning" not in json.dumps(snapshot)
        assert snapshot["progress"]["procedure"] == "tenant"
        if reject_count == 3:
            assert snapshot["messages"][-1]["text"] == outcome.error.message
            assert snapshot["messages"][-1]["sources"] == []
        async with database(dsn, identity) as db:
            steps = await (
                await db.connection.execute(
                    "SELECT kind, input, output FROM agent_run_step WHERE run_id = %s",
                    (run.run_id,),
                )
            ).fetchall()
            assert sum(step["kind"] == "tool" for step in steps) == 1
            audit = json.dumps(steps)
            assert all(draft in audit for draft in drafts)
            assert "private rejected reasoning" in audit
        checked = json.loads(judge.requests[0].input[0].content)
        assert checked["material"]["progress"]["procedure"] == "tenant"
        assert checked["material"]["sources"]
        assert all(request.tools == () for request in judge.requests)
        followup = Turns("Continue preparing.")
        await turn(
            environment(dsn, followup, identity),
            "What next?",
            run.conversation_id,
        )
        assert not any(
            draft in str(followup.requests[0].input) for draft in drafts
        )
        if reject_count == 3:
            assert outcome.error.message not in str(followup.requests[0].input)

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["malformed", "exception", "cancel"])
def test_judge_failure_never_releases_candidate_and_closes_connections(
    dsn, failure
):
    from lp_agent.types import TextEvent

    async def scenario():
        entered = asyncio.Event()

        class FailingJudge:
            async def stream(self, request):
                entered.set()
                if failure == "exception":
                    raise RuntimeError("Private provider diagnostics")
                if failure == "cancel":
                    await asyncio.Event().wait()
                yield ModelOutputItem(
                    item=ModelMessage(
                        role="assistant", content="not valid JSON"
                    )
                )
                yield ModelFinished(reason="stop")

        connections = TrackedConnections(dsn)
        env = environment(
            dsn,
            Turns("Private unchecked candidate"),
            uuid4().hex,
            connections=connections,
            judge=FailingJudge(),
        )
        async with LPAgent(environment=env) as agent:
            run = await agent.run(message="What help is available?")
            await asyncio.wait_for(entered.wait(), 5)
            if failure == "cancel":
                await run.cancel()
            outcome = await run.result()
            events = [event async for event in run.events()]
            assert not any(
                isinstance(event.payload, TextEvent) for event in events
            )
            assert "Private" not in outcome.model_dump_json()
            if failure == "cancel":
                assert outcome.state == "cancelled"
            else:
                assert outcome.error.code == "judge_failed"
            assert (await run.status()).state == outcome.state
        assert all(connection.closed for connection in connections.opened)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "court,topic,answers",
    [
        (None, None, ["franklin-county-oh", "eviction"]),
        ("franklin-county-oh", None, ["eviction"]),
        (None, "eviction", ["franklin-county-oh"]),
    ],
)
def test_partial_scope_static_replies_and_invalid_choice_preserve_question(
    dsn, court, topic, answers
):
    async def scenario():
        model, judge = Turns("I can help with eviction."), PassingJudge()
        env = environment(dsn, model, uuid4().hex, court, topic, judge=judge)
        async with LPAgent(environment=env) as agent:
            first = await agent.run(message="What eviction help is available?")
            assert (await first.result()).state == "completed"
            invalid = await agent.run(
                message="99", conversation_id=first.conversation_id
            )
            assert (await invalid.result()).text == (await first.result()).text
            for answer in answers:
                assert model.requests == judge.requests == []
                run = await agent.run(
                    message=answer, conversation_id=first.conversation_id
                )
                assert (await run.result()).state == "completed"
        assert len(model.requests) == len(judge.requests) == 1
        assert [item.content for item in model.requests[0].input] == [
            "What eviction help is available?"
        ]

    asyncio.run(scenario())


def test_off_topic_draft_is_corrected_before_any_answer_text_is_released(dsn):
    from lp_agent.types import TextEvent

    async def scenario():
        draft = "Here is an unrelated weather forecast."
        correction = "I can help you understand court procedures. What do you need help with?"
        model = Turns(draft, correction)
        judge = Turns(
            json.dumps(
                {
                    "approved": False,
                    "findings": [
                        {
                            "code": "off_topic",
                            "message": "Stay within the assistant's legal-system purpose.",
                        }
                    ],
                }
            ),
            '{"approved": true, "findings": []}',
        )
        env = environment(dsn, model, uuid4().hex, judge=judge)
        async with LPAgent(environment=env) as agent:
            run = await agent.run(message="What help can you offer?")
            events = [event async for event in run.events()]
            outcome = await run.result()
        assert outcome.state == "completed"
        assert [
            event.payload.delta
            for event in events
            if isinstance(event.payload, TextEvent)
        ] == [correction]
        assert model.requests[1].tools == ()
        assert "legal-system purpose" in model.requests[1].input[-1].content
        assert (
            json.loads(judge.requests[0].input[0].content)["candidate"]
            == draft
        )

    asyncio.run(scenario())
