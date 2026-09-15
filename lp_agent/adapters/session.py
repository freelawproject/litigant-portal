"""
Lazy connection ownership and store adapters for the agent database.

Only configuration is read from Django. Each operation owns its psycopg async
connection; preparation runs keep a dedicated connection for atomic effects.
"""

from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
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


def default_connection_options() -> Mapping[str, object]:
    """
    Read normalized default configuration without opening a Django connection.
    """
    from django.db import connections

    options = dict(connections["default"].get_connection_params())
    # A synchronous cursor class cannot be used by an AsyncConnection.
    options.pop("cursor_factory", None)
    # Django's adapters customize ORM value conversion. Agent rows use the
    # driver's own adapters and dict_row.
    options.pop("context", None)
    return options


class DatabaseConnections:
    """
    Create separately owned trusted and restricted connections on the caller's loop.
    """

    def __init__(
        self,
        options: Callable[
            [], Mapping[str, object]
        ] = default_connection_options,
    ) -> None:
        self._options = options

    async def connect(
        self, *, lookup: bool = False
    ) -> "AsyncConnection[DictRow]":
        from psycopg import AsyncConnection
        from psycopg.conninfo import make_conninfo
        from psycopg.rows import DictRow, dict_row

        try:
            options = dict(self._options())
            conninfo = options.pop("conninfo", "")
            threshold = options.pop("prepare_threshold", None)
            if not isinstance(conninfo, str) or not (
                threshold is None or type(threshold) is int
            ):
                raise ValueError("Invalid connection configuration.")
            options.setdefault("connect_timeout", 5)
            parameters: dict[str, str | int | None] = {}
            for key, value in options.items():
                if not isinstance(value, str | int) and value is not None:
                    raise ValueError("Invalid connection parameter.")
                parameters[key] = value
            connection = await AsyncConnection[DictRow].connect(
                make_conninfo(conninfo, **parameters),
                autocommit=True,
                row_factory=dict_row,
                prepare_threshold=threshold,
            )
            try:
                await connection.execute(
                    "SET ROLE agent_dev_lookup"
                    if lookup
                    else "SET ROLE agent_dev_crud"
                )
                return connection
            except BaseException:
                await connection.close()
                raise
        except Exception:
            raise AgentStorageError() from None

    @asynccontextmanager
    async def connection(self) -> AsyncIterator["AsyncConnection[DictRow]"]:
        connection = await self.connect()
        try:
            yield connection
        finally:
            await connection.close()


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
    ) -> None:
        from lp_agent.adapters.db import DatabaseRunStore

        async with self.connections.connection() as connection:
            await DatabaseRunStore(connection).commit_checkpoint(
                access=access,
                checkpoint=checkpoint,
                status=status,
                outcome=outcome,
            )


class DatabasePreparationService:
    """
    Bind access and provider configuration without retrieving corpus eagerly.
    """

    def __init__(
        self,
        connections: DatabaseConnections,
        access: AccessContext,
        scope: Scope,
        model_identifier: str,
    ) -> None:
        self.connections = connections
        self.access = access
        self.scope = scope
        self.model_identifier = model_identifier

    async def open(self) -> PreparationSession:
        from lp_agent.adapters.preparation import DatabasePreparationSession

        return DatabasePreparationSession(
            await self.connections.connect(),
            connections=self.connections,
            access=self.access,
            scope=self.scope,
            model_identifier=self.model_identifier,
        )
