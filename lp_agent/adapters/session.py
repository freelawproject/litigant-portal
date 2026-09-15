"""
Lazy connection ownership and store adapters for the agent database.

Only configuration is read from Django. Each operation owns its psycopg async
connection; preparation runs keep a dedicated connection for atomic effects.
"""

from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from typing import TYPE_CHECKING

from lp_agent.errors import AgentStorageError
from lp_agent.preparation import PreparationSession
from lp_agent.types import (
    AccessContext,
    AgentConfiguration,
    Conversation,
    RunCheckpoint,
    RunOutcome,
    RunRequest,
    RunStatus,
    Scope,
    ScopeSelection,
)

if TYPE_CHECKING:
    from psycopg import AsyncConnection
    from psycopg.rows import DictRow


def django_database_dsn() -> str:
    """
    Reuse the configured application database without sharing its connection.
    """
    from django.conf import settings
    from psycopg.conninfo import make_conninfo

    config = settings.DATABASES["default"]
    return make_conninfo(
        dbname=config["NAME"],
        user=config["USER"],
        password=config["PASSWORD"],
        host=config["HOST"],
        port=config["PORT"],
    )


def default_connection_options() -> Mapping[str, object]:
    """
    Read host configuration lazily; credentials never enter serialized run data.
    """
    from django.conf import settings

    from lp_agent.errors import AgentValidationError

    if settings.LP_AGENT_USE_DJANGO_DB:
        if settings.DEPLOYMENT_ENV not in {"dev", "qa"}:
            raise AgentValidationError(
                "LP_AGENT_USE_DJANGO_DB is only available in dev and QA."
            )
        dsn = django_database_dsn()
        return {
            "writer": dsn,
            "lookup": dsn,
            "court": None
            if settings.DEPLOYMENT_ENV == "qa"
            else settings.CORPUS_COURT,
            "shared_database": True,
        }
    return {
        "writer": settings.LP_AGENT_WRITER_DSN,
        "lookup": settings.LP_AGENT_LOOKUP_DSN,
        "court": settings.CORPUS_COURT,
    }


class DatabaseConnections:
    """
    Own short-lived connections through the shared writer and lookup factories.
    """

    def __init__(
        self,
        options: Callable[
            [], Mapping[str, object]
        ] = default_connection_options,
    ) -> None:
        self._options = options

    @property
    def court(self) -> str | None:
        value = self._options().get("court")
        return value if isinstance(value, str) else None

    @asynccontextmanager
    async def connection(
        self, *, lookup: bool = False
    ) -> AsyncIterator["AsyncConnection[DictRow]"]:
        from psycopg import Error

        from lp_agent.adapters.connections import (
            agent_connection,
            lookup_connection,
        )
        from lp_agent.errors import AgentValidationError

        try:
            options = self._options()
            dsn = options.get("lookup" if lookup else "writer")
            if not isinstance(dsn, str) or not dsn.strip():
                raise AgentValidationError(
                    "Agent database credentials are not configured."
                )
            factory = (
                lookup_connection
                if lookup and not options.get("shared_database", False)
                else agent_connection
            )
            async with factory(dsn) as connection:
                yield connection
        except Error:
            raise AgentStorageError() from None


class LazyConversationStore:
    """
    Preserve the conversation protocol without sharing a run's transaction.
    """

    def __init__(self, connections: DatabaseConnections) -> None:
        self.connections = connections

    async def create(
        self, *, access: AccessContext, scope: ScopeSelection
    ) -> Conversation:
        from lp_agent.adapters.db import DatabaseConversationStore

        async with self.connections.connection() as connection:
            return await DatabaseConversationStore(connection).create(
                access=access, scope=scope
            )

    async def get(
        self, *, access: AccessContext, conversation_id: str
    ) -> Conversation:
        from lp_agent.adapters.db import DatabaseConversationStore

        async with self.connections.connection() as connection:
            return await DatabaseConversationStore(connection).get(
                access=access, conversation_id=conversation_id
            )

    async def bind_scope(
        self, *, access: AccessContext, conversation_id: str, scope: Scope
    ) -> None:
        from lp_agent.adapters.db import DatabaseConversationStore

        async with self.connections.connection() as connection:
            await DatabaseConversationStore(connection).bind_scope(
                access=access, conversation_id=conversation_id, scope=scope
            )


class LazyRunStore:
    """
    Open short-lived connections for status, recovery, and independent store calls.
    """

    def __init__(self, connections: DatabaseConnections) -> None:
        self.connections = connections

    async def create(
        self,
        *,
        access: AccessContext,
        conversation_id: str,
        request: RunRequest,
        configuration: AgentConfiguration,
    ) -> RunStatus:
        from lp_agent.adapters.db import DatabaseRunStore

        async with self.connections.connection() as connection:
            return await DatabaseRunStore(connection).create(
                access=access,
                conversation_id=conversation_id,
                request=request,
                configuration=configuration,
            )

    async def status(self, *, access: AccessContext, run_id: str) -> RunStatus:
        from lp_agent.adapters.db import DatabaseRunStore

        async with self.connections.connection() as connection:
            return await DatabaseRunStore(connection).status(
                access=access, run_id=run_id
            )

    async def outcome(
        self, *, access: AccessContext, run_id: str
    ) -> RunOutcome | None:
        from lp_agent.adapters.db import DatabaseRunStore

        async with self.connections.connection() as connection:
            return await DatabaseRunStore(connection).outcome(
                access=access, run_id=run_id
            )

    async def checkpoint(
        self, *, access: AccessContext, run_id: str
    ) -> RunCheckpoint | None:
        from lp_agent.adapters.db import DatabaseRunStore

        async with self.connections.connection() as connection:
            return await DatabaseRunStore(connection).checkpoint(
                access=access, run_id=run_id
            )

    async def commit_checkpoint(
        self,
        *,
        access: AccessContext,
        checkpoint: RunCheckpoint,
        status: RunStatus,
        outcome: RunOutcome | None = None,
    ) -> RunCheckpoint:
        from lp_agent.adapters.db import DatabaseRunStore

        async with self.connections.connection() as connection:
            return await DatabaseRunStore(connection).commit_checkpoint(
                access=access,
                checkpoint=checkpoint,
                status=status,
                outcome=outcome,
            )


class DatabasePreparationService:
    """
    Open a persisted turn before its optional court/topic selection is complete.
    """

    def __init__(
        self,
        connections: DatabaseConnections,
        access: AccessContext,
        model_identifier: str,
        judge_identifier: str | None = None,
    ) -> None:
        self.connections = connections
        self.access = access
        self.model_identifier = model_identifier
        self.judge_identifier = judge_identifier

    async def open(self, scope: ScopeSelection) -> PreparationSession:
        from lp_agent.adapters.preparation import DatabasePreparationSession

        stack = AsyncExitStack()
        try:
            connection = await stack.enter_async_context(
                self.connections.connection()
            )
            return DatabasePreparationSession(
                connection,
                connections=self.connections,
                access=self.access,
                scope=scope,
                model_identifier=self.model_identifier,
                judge_identifier=self.judge_identifier,
                stack=stack,
            )
        except BaseException:
            await stack.aclose()
            raise
