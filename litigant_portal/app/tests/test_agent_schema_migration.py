"""
Verify schema installation and adoption using disposable PostgreSQL databases.
"""

from importlib import import_module
from types import SimpleNamespace

import pytest
from psycopg import Connection, sql

from lp_agent.tests.providers import test_database as database_fixtures

pytestmark = pytest.mark.postgres
database_dsns = database_fixtures.database_dsns
migration = import_module("litigant_portal.app.migrations.0019_agent_schema")


def editor(connection):
    """
    Supply the migration's normal cursor interface on an isolated database.
    """
    return SimpleNamespace(
        connection=SimpleNamespace(
            vendor="postgresql", cursor=connection.cursor
        )
    )


def test_fresh_install_and_recognized_adoption_preserve_data(database_dsns):
    with Connection.connect(database_dsns["admin"]) as connection:
        tables = connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
        ).fetchall()
        connection.execute(
            sql.SQL("DROP TABLE {}").format(
                sql.SQL(", ").join(
                    sql.Identifier("public", row[0]) for row in tables
                )
            )
        )
        functions = connection.execute(
            "SELECT oid::regprocedure::text FROM pg_proc WHERE pronamespace = 'public'::regnamespace AND proname LIKE 'agent!_%' ESCAPE '!'"
        ).fetchall()
        connection.execute(
            sql.SQL("DROP FUNCTION {}").format(
                sql.SQL(", ").join(sql.SQL(row[0]) for row in functions)
            )
        )
        migration.install_schema(None, editor(connection))
        assert (
            connection.execute(
                "SELECT count(*) FROM pg_tables WHERE schemaname = 'public'"
            ).fetchone()[0]
            == 27
        )
        connection.execute(
            "INSERT INTO agent_user (user_id) VALUES ('preserved')"
        )
        migration.install_schema(None, editor(connection))
        assert connection.execute(
            "SELECT user_id FROM agent_user"
        ).fetchall() == [("preserved",)]


@pytest.mark.parametrize("change", ["marker", "table", "function"])
def test_unrecognized_existing_schema_is_rejected(database_dsns, change):
    with Connection.connect(database_dsns["admin"]) as connection:
        try:
            with connection.transaction():
                connection.execute(
                    sql.SQL("COMMENT ON TABLE agent_user IS {}").format(
                        sql.Literal(migration.MARKER)
                    )
                )
                if change == "marker":
                    connection.execute(
                        "COMMENT ON TABLE agent_user IS 'unknown'"
                    )
                elif change == "table":
                    connection.execute(
                        "CREATE TABLE agent_unknown (id integer)"
                    )
                else:
                    connection.execute(
                        "CREATE FUNCTION agent_unknown() RETURNS integer LANGUAGE sql AS 'SELECT 1'"
                    )
                migration.install_schema(None, editor(connection))
        except RuntimeError as error:
            assert "Unrecognized existing agent schema" in str(error)
        else:
            pytest.fail("Migration adopted an unknown installation")
