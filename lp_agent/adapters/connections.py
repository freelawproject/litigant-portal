"""
Caller-owned connections for trusted writes and restricted agent lookups.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row

from lp_agent.errors import AgentValidationError


def validate_connection(connection: AsyncConnection[DictRow]) -> None:
    """
    Reject connection settings that change adapter rows or commit behavior.
    """
    if not connection.autocommit or connection.row_factory is not dict_row:
        raise AgentValidationError(
            "Agent database connections require dict_row and autocommit=True."
        )


@asynccontextmanager
async def agent_connection(
    dsn: str,
) -> AsyncIterator[AsyncConnection[DictRow]]:
    """
    Open a trusted connection using host-supplied writer credentials.

    Create connections inside the process and event loop that will use them.
    Each concurrent unit of work needs its own connection. The context closes
    it on exit; db.transaction() groups writes without spanning model calls.
    """
    async with await AsyncConnection[DictRow].connect(
        dsn, row_factory=dict_row, autocommit=True
    ) as connection:
        yield connection


@asynccontextmanager
async def lookup_connection(
    dsn: str,
) -> AsyncIterator[AsyncConnection[DictRow]]:
    """
    Open a login that inherits only the agent_dev_lookup permission group.

    Validate the session login, its memberships, and agent object privileges.
    A privileged login narrowed with SET ROLE is not a lookup connection.
    The host still authenticates the user and supplies verified tool context.
    """
    async with agent_connection(dsn) as connection:
        row = await (
            await connection.execute(
                """
                WITH roles AS (
                    SELECT * FROM pg_roles
                    WHERE pg_has_role(session_user, oid, 'MEMBER')
                )
                SELECT current_user = session_user
                    AND EXISTS (
                        SELECT FROM roles WHERE rolname = 'agent_dev_lookup'
                            AND pg_has_role(session_user, oid, 'USAGE')
                    )
                    AND NOT EXISTS (
                        SELECT FROM roles
                        WHERE rolname NOT IN (session_user, 'agent_dev_lookup')
                            OR rolsuper OR rolcreatedb OR rolcreaterole
                            OR rolreplication OR rolbypassrls
                    )
                    AND NOT has_schema_privilege(session_user, 'public', 'CREATE')
                    AND NOT EXISTS (
                        SELECT FROM pg_class c
                        WHERE c.relnamespace = 'public'::regnamespace
                            AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
                            AND c.relname IN ('agent_memory', 'agent_memory_source', 'agent_prompt', 'agent_run', 'agent_run_step', 'app_chatmessage', 'app_chatthread', 'app_corpus_document', 'app_court', 'app_court_topic', 'app_document', 'app_document_chunk', 'app_fact_evidence', 'app_import_audit', 'app_matter', 'app_matter_document', 'app_matter_procedure', 'app_message_attachment', 'app_phase_document', 'app_phase_progress', 'app_promptartifact', 'app_topic', 'app_topicflow', 'app_topicflowdeadline', 'app_topicflowinterviewpage', 'app_topicflowinterviewvariable', 'app_useridentity', 'app_variable', 'app_variableanswer')
                            AND (c.relowner IN (SELECT oid FROM roles)
                                OR has_table_privilege(session_user, c.oid,
                                    'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER'))
                    )
                    AND NOT EXISTS (
                        SELECT FROM pg_proc p
                        WHERE p.pronamespace = 'public'::regnamespace
                            AND p.proname LIKE 'agent!_%' ESCAPE '!'
                            AND p.proname NOT IN (
                                'agent_search_private', 'agent_get_private_source',
                                'agent_search_corpus', 'agent_get_corpus_source'
                            )
                            AND has_function_privilege(session_user, p.oid, 'EXECUTE')
                    ) AS allowed
                """
            )
        ).fetchone()
        if row is None or not row["allowed"]:
            raise AgentValidationError(
                "Use a dedicated login with only agent lookup permissions."
            )
        yield connection
