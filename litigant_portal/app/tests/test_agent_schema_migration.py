"""
Verify schema installation and adoption using disposable PostgreSQL databases.
"""

from hashlib import sha256
from importlib import import_module
from types import SimpleNamespace

import pytest
from psycopg import Connection, sql
from psycopg.conninfo import conninfo_to_dict

from lp_agent.tests.providers import test_database as database_fixtures

pytestmark = pytest.mark.postgres
database_dsns = database_fixtures.database_dsns
migration = import_module("litigant_portal.app.migrations.0019_agent_schema")
vector_migration = import_module(
    "litigant_portal.app.migrations.0020_defer_agent_vectors"
)


def editor(connection):
    """
    Supply the migration's normal cursor interface on an isolated database.
    """
    return SimpleNamespace(
        connection=SimpleNamespace(
            vendor="postgresql", cursor=connection.cursor
        )
    )


def test_fresh_install_without_pgvector_as_application_login(database_dsns):
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
        role = sql.Identifier(conninfo_to_dict(database_dsns["crud"])["user"])
        connection.execute(
            sql.SQL(
                "GRANT USAGE, CREATE ON SCHEMA public TO {}, agent_dev_reader"
            ).format(role)
        )
        connection.execute(
            sql.SQL("GRANT agent_dev_reader TO {}").format(role)
        )

    with Connection.connect(database_dsns["crud"]) as connection:
        assert connection.execute(
            "SELECT rolsuper, rolcreaterole FROM pg_roles WHERE rolname = current_user"
        ).fetchone() == (False, False)
        migration.install_schema(None, editor(connection))
        vector_migration.remove_unused_vectors(None, editor(connection))
        assert (
            connection.execute(
                "SELECT FROM pg_extension WHERE extname = 'vector'"
            ).fetchone()
            is None
        )
        assert (
            connection.execute(
                "SELECT FROM information_schema.columns WHERE table_schema = 'public' "
                "AND table_name = 'agent_document_chunk' AND column_name = 'embedding'"
            ).fetchone()
            is None
        )
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


@pytest.fixture
def legacy_vectors(database_dsns):
    """
    Restore the original vector column and trigger in a rolled-back fixture.
    """
    with Connection.connect(database_dsns["admin"]) as connection:
        if (
            connection.execute(
                "SELECT FROM pg_available_extensions WHERE name = 'vector'"
            ).fetchone()
            is None
        ):
            pytest.skip("Legacy vector upgrade requires pgvector availability")
        with connection.transaction(force_rollback=True):
            connection.execute(
                "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public"
            )
            connection.execute(
                "ALTER TABLE agent_document_chunk ADD COLUMN embedding public.vector"
            )
            definition = connection.execute(
                "SELECT pg_get_functiondef('public.agent_validate_record()'::regprocedure)"
            ).fetchone()[0]
            connection.execute(
                definition.replace(
                    "length(body) >",
                    "(doc.embedding_dimensions IS NULL AND embedding IS NOT NULL) OR "
                    "(doc.embedding_dimensions IS NOT NULL AND (embedding IS NULL OR "
                    "public.vector_dims(embedding) <> doc.embedding_dimensions)) OR length(body) >",
                    1,
                )
            )
            connection.execute(
                sql.SQL("COMMENT ON TABLE agent_user IS {}").format(
                    sql.Literal(migration.LEGACY_MARKER)
                )
            )
            yield connection


@pytest.mark.parametrize("has_embedding", [False, True])
def test_legacy_upgrade_preserves_text_and_refuses_embeddings(
    legacy_vectors, has_embedding
):
    connection = legacy_vectors
    connection.execute(
        "INSERT INTO agent_user (user_id) VALUES ('legacy-user')"
    )
    document_id = connection.execute(
        """
        INSERT INTO agent_document (
            owner_kind, owner_user_id, key, title, category, version,
            s3_bucket, s3_key, sha256, byte_size, media_type, state, created_by,
            index_revision, index_state, parser_version, chunker_version,
            chunk_count, indexed_at, embedding_provider, embedding_model,
            embedding_dimensions
        ) VALUES (
            'user', 'legacy-user', 'legacy', 'Legacy document', 'upload', 1,
            'test', 'legacy.txt', repeat('a', 64), 4, 'text/plain', 'private',
            'legacy-user', 1, 'ready', 'test', 'test', 1, now(), %s, %s, %s
        ) RETURNING id
        """,
        ("test", "test", 2) if has_embedding else (None, None, None),
    ).fetchone()[0]
    connection.execute(
        """
        INSERT INTO agent_document_chunk (
            document_id, ordinal, body, locator, text_sha256, embedding
        ) VALUES (%s, 1, 'Text', '{"page": 1}', %s, %s::public.vector)
        """,
        (
            document_id,
            sha256(b"Text").hexdigest(),
            "[0.1,0.2]" if has_embedding else None,
        ),
    )
    connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
    before = connection.execute(
        "SELECT to_jsonb(d), to_jsonb(c) - 'embedding' FROM agent_document d "
        "JOIN agent_document_chunk c ON c.document_id = d.id WHERE d.id = %s",
        (document_id,),
    ).fetchone()
    migration.install_schema(None, editor(connection))

    if has_embedding:
        with pytest.raises(RuntimeError, match="will not discard"):
            vector_migration.remove_unused_vectors(None, editor(connection))
        assert connection.execute(
            "SELECT embedding IS NOT NULL FROM agent_document_chunk WHERE document_id = %s",
            (document_id,),
        ).fetchone()[0]
        return

    vector_migration.remove_unused_vectors(None, editor(connection))
    assert (
        connection.execute(
            "SELECT to_jsonb(d), to_jsonb(c) FROM agent_document d "
            "JOIN agent_document_chunk c ON c.document_id = d.id WHERE d.id = %s",
            (document_id,),
        ).fetchone()
        == before
    )
    assert (
        "vector_dims"
        not in connection.execute(
            "SELECT pg_get_functiondef('public.agent_validate_record()'::regprocedure)"
        ).fetchone()[0]
    )
    assert (
        connection.execute(
            "SELECT obj_description('agent_user'::regclass, 'pg_class')"
        ).fetchone()[0]
        == migration.MARKER
    )
    assert (
        connection.execute(
            "SELECT FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        is not None
    )
    migration.install_schema(None, editor(connection))


def test_vector_upgrade_rejects_unknown_schema(database_dsns):
    with (
        Connection.connect(database_dsns["admin"]) as connection,
        connection.transaction(force_rollback=True),
    ):
        connection.execute("COMMENT ON TABLE agent_user IS 'unknown'")
        with pytest.raises(RuntimeError, match="Unrecognized agent schema"):
            vector_migration.remove_unused_vectors(None, editor(connection))


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
