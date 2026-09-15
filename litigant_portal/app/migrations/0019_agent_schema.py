"""
Install the experimental agent schema without introducing Django ORM models.

The pre-release SQL snapshot omits unused pgvector storage. Migration 0020
upgrades installations of the earlier snapshot. Future schema changes require
another migration, even while the agent remains a proof of concept.
"""

import hashlib
import re
from pathlib import Path

from django.db import migrations
from psycopg import sql

SQL_DIR = Path(__file__).with_name("agent_sql_0019")
SQL_FILES = ("agent_tables.sql", "agent_constraints.sql", "agent_search.sql")
FINGERPRINT = (
    "0bdaf840ca00defac0fb0c8e1d52595a7d5426f6e823b1fa6c41eca74279666c"
)
MARKER = "lp-agent-local-v2:" + FINGERPRINT
LEGACY_MARKER = (
    "lp-agent-local-v2:"
    "2f7497f8142e38d3c9c3bbf54e232883db9072107cd34873bbad736ff7c171f9"
)


def read_bundle():
    """
    Verify the frozen schema shared with the compatibility migration.
    """
    bundle = "\n\n".join((SQL_DIR / name).read_text() for name in SQL_FILES)
    if hashlib.sha256(bundle.encode()).hexdigest() != FINGERPRINT:
        raise RuntimeError("The frozen 0019 agent SQL bundle has changed.")
    return bundle


def install_schema(apps, schema_editor):
    """
    Install atomically or adopt the recognized pre-migration local installation.
    """
    if schema_editor.connection.vendor != "postgresql":
        raise RuntimeError("The agent schema requires PostgreSQL.")
    bundle = read_bundle()
    tables = sorted(re.findall(r"CREATE TABLE public\.(agent_\w+)", bundle))
    functions = sorted(
        re.findall(r"CREATE FUNCTION public\.(agent_\w+)\(", bundle)
    )
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(173904, 1)")
        cursor.execute(
            """
            SELECT relname FROM pg_class
            WHERE relnamespace = 'public'::regnamespace
                AND relname LIKE 'agent!_%' ESCAPE '!'
                AND relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
            ORDER BY relname
            """
        )
        installed_tables = [row[0] for row in cursor.fetchall()]
        cursor.execute(
            """
            SELECT proname FROM pg_proc
            WHERE pronamespace = 'public'::regnamespace
                AND proname LIKE 'agent!_%' ESCAPE '!'
            ORDER BY proname
            """
        )
        installed_functions = [row[0] for row in cursor.fetchall()]
        if installed_tables or installed_functions:
            cursor.execute(
                "SELECT obj_description(to_regclass('public.agent_user'), 'pg_class')"
            )
            if (
                cursor.fetchone()[0] not in {MARKER, LEGACY_MARKER}
                or installed_tables != tables
                or installed_functions != functions
            ):
                raise RuntimeError(
                    "Unrecognized existing agent schema; no changes made. "
                    "Review the installation before applying migration 0019."
                )
            return
        cursor.execute(bundle)
        cursor.execute(
            sql.SQL("COMMENT ON TABLE public.agent_user IS {}").format(
                sql.Literal(MARKER)
            )
        )


class Migration(migrations.Migration):
    dependencies = [("app", "0018_bedrock_model_choices")]

    # Reversing retains agent data. Reapplying adopts the recognized schema;
    # schema corrections use subsequent migrations instead of destructive drops.
    operations = [
        migrations.RunPython(install_schema, migrations.RunPython.noop)
    ]
