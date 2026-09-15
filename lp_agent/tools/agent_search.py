"""
Model-callable search through the four restricted PostgreSQL lookup functions.
"""

from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import JsonValue, TypeAdapter, ValidationError

from lp_agent.errors import AgentError, AgentValidationError
from lp_agent.types import (
    AccessContext,
    AgentSearchQuery,
    AgentSourceQuery,
    ToolDefinition,
)

if TYPE_CHECKING:
    from psycopg import AsyncConnection
    from psycopg.rows import DictRow

SEARCH_TOOLS = (
    ToolDefinition(
        name="agent_search",
        description="Search published court material or permitted personal information. Choose one category per call.",
        parameters=AgentSearchQuery.model_json_schema(),
    ),
    ToolDefinition(
        name="agent_get_source",
        description="Retrieve a bounded source excerpt using an ID returned by agent_search.",
        parameters=AgentSourceQuery.model_json_schema(),
    ),
)


class AgentSearch:
    """
    Bind trusted context to a lookup-role connection before exposing the tools.

    Use lookup_connection() to verify the dedicated restricted login; manually
    supplied connections must have the same privileges and configuration.
    The host authenticates access and supplies its current recall policy. These
    values never come from model arguments. Other search sources can be added
    here when implemented; the database path always uses stored functions.
    """

    def __init__(
        self,
        connection: "AsyncConnection[DictRow]",
        *,
        access: AccessContext,
        run_id: str,
        host_policy: dict[str, JsonValue],
    ):
        from lp_agent.adapters.connections import validate_connection

        validate_connection(connection)
        self.connection = connection
        self.access = access
        self.run_id = UUID(run_id)
        self.host_policy = TypeAdapter(dict[str, JsonValue]).validate_python(
            host_policy
        )

    async def search(
        self, query: AgentSearchQuery
    ) -> tuple[dict[str, JsonValue], ...]:
        """
        Search one allowed category using a fixed parameterized function call.
        """
        from psycopg.types.json import Jsonb

        async with self.connection.transaction():
            if query.category == "court_corpus":
                cursor = await self.connection.execute(
                    "SELECT public.agent_search_corpus(%s, %s, %s, %s) AS result",
                    (
                        self.access.identity_id,
                        self.run_id,
                        query.query,
                        query.limit,
                    ),
                )
            else:
                cursor = await self.connection.execute(
                    "SELECT public.agent_search_private(%s, %s, %s, %s, %s, %s, %s) AS result",
                    (
                        self.access.identity_id,
                        self.run_id,
                        Jsonb(self.host_policy),
                        query.query,
                        [query.category],
                        Jsonb({}),
                        query.limit,
                    ),
                )
            return tuple(
                TypeAdapter(dict[str, JsonValue]).validate_python(
                    row["result"]
                )
                for row in await cursor.fetchall()
            )

    async def get_source(
        self, query: AgentSourceQuery
    ) -> tuple[dict[str, JsonValue], ...]:
        """
        Recheck access and fetch an excerpt; this does not download the file.
        """
        from psycopg.types.json import Jsonb

        try:
            source_id = UUID(query.source_id)
        except ValueError:
            raise AgentValidationError(
                "Source ID must be a UUID returned by search."
            ) from None
        async with self.connection.transaction():
            if query.category == "court_corpus":
                cursor = await self.connection.execute(
                    "SELECT public.agent_get_corpus_source(%s, %s, %s) AS result",
                    (self.access.identity_id, self.run_id, source_id),
                )
            else:
                cursor = await self.connection.execute(
                    "SELECT public.agent_get_private_source(%s, %s, %s, %s, %s, %s) AS result",
                    (
                        self.access.identity_id,
                        self.run_id,
                        Jsonb(self.host_policy),
                        query.category,
                        source_id,
                        Jsonb({}),
                    ),
                )
            return tuple(
                TypeAdapter(dict[str, JsonValue]).validate_python(
                    row["result"]
                )
                for row in await cursor.fetchall()
            )

    async def call(
        self, name: str, arguments: str
    ) -> tuple[dict[str, JsonValue], ...]:
        """
        Validate model arguments and keep database diagnostics out of tool output.
        """
        from psycopg import Error

        try:
            if name == "agent_search":
                return await self.search(
                    AgentSearchQuery.model_validate_json(arguments)
                )
            if name == "agent_get_source":
                return await self.get_source(
                    AgentSourceQuery.model_validate_json(arguments)
                )
            raise AgentValidationError("Unknown search tool.")
        except ValidationError as error:
            raise AgentValidationError.from_validation_error(
                error, models=(AgentSearchQuery, AgentSourceQuery)
            ) from None
        except Error:
            raise AgentError("Database search is unavailable.") from None
