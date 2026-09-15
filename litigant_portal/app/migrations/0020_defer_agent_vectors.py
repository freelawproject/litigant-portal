"""
Remove unused vector storage from installations of the original PoC snapshot.
"""

import re
from importlib import import_module

from django.db import migrations
from psycopg import sql

schema = import_module("litigant_portal.app.migrations.0019_agent_schema")


def remove_unused_vectors(apps, schema_editor):
    """
    Preserve agent data and retain any extension installed by the database owner.
    """
    bundle = schema.read_bundle()
    definition = re.search(
        r"CREATE FUNCTION public\.agent_validate_record\(\).*?\n\$\$;",
        bundle,
        re.DOTALL,
    ).group()
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(173904, 1)")
        cursor.execute(
            "SELECT obj_description(to_regclass('public.agent_user'), 'pg_class')"
        )
        marker = cursor.fetchone()[0]
        if marker == schema.MARKER:
            return
        if marker != schema.LEGACY_MARKER:
            raise RuntimeError(
                "Unrecognized agent schema; no changes made by migration 0020."
            )
        cursor.execute(
            "LOCK TABLE public.agent_document_chunk IN ACCESS EXCLUSIVE MODE"
        )
        cursor.execute(
            "SELECT EXISTS (SELECT FROM public.agent_document_chunk "
            "WHERE embedding IS NOT NULL)"
        )
        if cursor.fetchone()[0]:
            raise RuntimeError(
                "Agent embeddings contain data; migration 0020 will not "
                "discard them. Preserve that data before removing vector storage."
            )
        cursor.execute(
            definition.replace(
                "CREATE FUNCTION", "CREATE OR REPLACE FUNCTION", 1
            )
        )
        cursor.execute(
            "ALTER TABLE public.agent_document_chunk DROP COLUMN embedding"
        )
        cursor.execute(
            sql.SQL("COMMENT ON TABLE public.agent_user IS {}").format(
                sql.Literal(schema.MARKER)
            )
        )


class Migration(migrations.Migration):
    dependencies = [("app", "0019_agent_schema")]

    operations = [
        migrations.RunPython(remove_unused_vectors, migrations.RunPython.noop)
    ]
