"""
Restore vector storage and narrow the existing QA reader role to search calls.
"""

import re
from importlib import import_module

from django.conf import settings
from django.db import migrations
from psycopg import sql

schema = import_module("litigant_portal.app.migrations.0019_agent_schema")
SEARCH_FUNCTIONS = (
    "agent_search_private",
    "agent_get_private_source",
    "agent_search_corpus",
    "agent_get_corpus_source",
)


def restore_vectors_and_qa_search(apps, schema_editor):
    """
    Upgrade in place using the extension and role membership supplied by infra.
    """
    bundle = schema.read_bundle()
    definition = re.search(
        r"CREATE FUNCTION public\.agent_validate_record\(\).*?\n\$\$;",
        bundle,
        re.DOTALL,
    ).group()
    definition = (
        definition.replace("CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1)
        .replace(
            "            length(body) >",
            "            (doc.embedding_dimensions IS NULL AND embedding IS NOT NULL) OR\n"
            "            (doc.embedding_dimensions IS NOT NULL AND (embedding IS NULL OR public.vector_dims(embedding) <> doc.embedding_dimensions)) OR\n"
            "            length(body) >",
            1,
        )
        .replace(
            "Active index must contain its declared bounded chunks'",
            "Active index must contain its declared bounded chunks and matching embeddings'",
            1,
        )
    )
    qa_shared = (
        settings.DEPLOYMENT_ENV == "qa" and settings.LP_AGENT_USE_DJANGO_DB
    )
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(173904, 1)")
        cursor.execute(
            "SELECT obj_description(to_regclass('public.agent_user'), 'pg_class')"
        )
        if cursor.fetchone()[0] not in {schema.MARKER, schema.QA_MARKER}:
            raise RuntimeError(
                "Unrecognized agent schema; migration 0021 stopped."
            )
        if qa_shared:
            cursor.execute(
                "SELECT EXISTS (SELECT FROM pg_extension WHERE extname = 'vector' "
                "AND extnamespace = 'public'::regnamespace)"
            )
            if not cursor.fetchone()[0]:
                raise RuntimeError(
                    "QA requires the vector extension in public."
                )
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM pg_roles r WHERE rolname = 'agent_dev_reader'
                        AND NOT (rolcanlogin OR rolsuper OR rolcreatedb OR
                            rolcreaterole OR rolreplication OR rolbypassrls)
                        AND pg_has_role(current_user, r.oid, 'MEMBER')
                        AND has_schema_privilege(r.oid, 'public', 'USAGE')
                        AND (NOT has_schema_privilege(r.oid, 'public', 'CREATE')
                            OR has_schema_privilege(current_user, 'public',
                                'CREATE WITH GRANT OPTION'))
                        AND NOT EXISTS (
                            SELECT FROM pg_roles other WHERE other.oid <> r.oid
                                AND pg_has_role(r.oid, other.oid, 'MEMBER')
                        )
                )
                """
            )
            if not cursor.fetchone()[0]:
                raise RuntimeError(
                    "QA requires the existing agent_dev_reader membership, "
                    "schema USAGE, and permission to remove its schema CREATE grant."
                )
            # Check SET permission before changing any database objects.
            cursor.execute("SET LOCAL ROLE agent_dev_reader")
            cursor.execute("RESET ROLE")
        else:
            cursor.execute(
                "CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public"
            )
        cursor.execute(
            "ALTER TABLE public.agent_document_chunk "
            "ADD COLUMN IF NOT EXISTS embedding public.vector"
        )
        cursor.execute(definition)
        if not qa_shared:
            return

        # Keep trusted SQL and function ownership with the application. Reuse
        # the reader membership already provisioned for this temporary QA PoC.
        for table in re.findall(r"CREATE TABLE public\.(agent_\w+)", bundle):
            cursor.execute(
                sql.SQL(
                    "REVOKE ALL ON TABLE public.{} FROM agent_dev_reader"
                ).format(sql.Identifier(table))
            )
        cursor.execute(
            "SELECT oid::regprocedure::text, proname FROM pg_proc "
            "WHERE pronamespace = 'public'::regnamespace "
            "AND proname LIKE 'agent!_%' ESCAPE '!'"
        )
        for signature, name in cursor.fetchall():
            if name in SEARCH_FUNCTIONS:
                cursor.execute(
                    sql.SQL("ALTER FUNCTION {} OWNER TO CURRENT_USER").format(
                        sql.SQL(signature)
                    )
                )
            cursor.execute(
                sql.SQL(
                    "REVOKE ALL ON FUNCTION {} FROM agent_dev_reader"
                ).format(sql.SQL(signature))
            )
            if name in SEARCH_FUNCTIONS:
                cursor.execute(
                    sql.SQL(
                        "GRANT EXECUTE ON FUNCTION {} TO agent_dev_reader"
                    ).format(sql.SQL(signature))
                )
        cursor.execute("REVOKE CREATE ON SCHEMA public FROM agent_dev_reader")
        cursor.execute(
            """
            SELECT has_schema_privilege('agent_dev_reader', 'public', 'CREATE')
                OR EXISTS (
                    SELECT FROM pg_class WHERE relnamespace = 'public'::regnamespace
                        AND relname LIKE 'agent!_%' ESCAPE '!'
                        AND relkind IN ('r', 'p', 'v', 'm', 'f')
                        AND has_table_privilege('agent_dev_reader', oid,
                            'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
                )
                OR EXISTS (
                    SELECT FROM pg_proc WHERE pronamespace = 'public'::regnamespace
                        AND proname LIKE 'agent!_%' ESCAPE '!'
                        AND proname NOT IN (
                            'agent_search_private', 'agent_get_private_source',
                            'agent_search_corpus', 'agent_get_corpus_source'
                        )
                        AND has_function_privilege('agent_dev_reader', oid, 'EXECUTE')
                )
            """
        )
        if cursor.fetchone()[0]:
            raise RuntimeError(
                "QA reader still has access beyond stored search functions."
            )


class Migration(migrations.Migration):
    dependencies = [("app", "0020_defer_agent_vectors")]

    # Keep restored vector data and the narrower permissions on a code rollback.
    operations = [
        migrations.RunPython(
            restore_vectors_and_qa_search, migrations.RunPython.noop
        )
    ]
