#!/usr/bin/env python3
"""
Install the experimental agent schema in this checkout's local Compose database.

Uses only Python's standard library, Docker, and the container's psql. Run with
--status to inspect or --sql to print SQL. Installation is transactional and
repeatable; changed SQL is rejected against an existing installation instead
of dropping tables or hiding drift.
"""

import argparse
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

# Temporary setup helper for the experimental agent database schema.
ROOT = Path(__file__).resolve().parents[4]
SQL_DIR = ROOT / "litigant_portal/app/migrations/agent_sql_0019"
SQL_FILES = ("agent_tables.sql", "agent_constraints.sql", "agent_search.sql")
MARKER = "lp-agent-local-v2:"
PREVIOUS_INSTALLATION = (
    "lp-agent-local-v1:"
    "099cfd1313d2c43648878b7609629f4496e13a306b72f39334f11e35b1444995"
)
REMOVED_TABLES = (
    "agent_procedure_version",
    "agent_prompt_version",
    "agent_prompt_binding",
    "agent_document_version",
    "agent_document_index",
    "agent_embedding_profile",
    "agent_run_context",
    "agent_run_checkpoint",
    "agent_instruction_artifact",
)


def command(args, *, input_text=None):
    """
    Execute an argument list without a shell or exposing environment values.
    """
    result = subprocess.run(
        args, input=input_text, text=True, capture_output=True, check=False
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def compose_command():
    """
    Restrict operations to the checkout's Compose service on a local Docker socket.
    """
    endpoint = os.environ.get("DOCKER_HOST")
    if not endpoint:
        endpoint = command(
            [
                "docker",
                "context",
                "inspect",
                "--format",
                '{{(index .Endpoints "docker").Host}}',
            ]
        )
    if not endpoint.startswith(("unix://", "npipe://")):
        raise RuntimeError(
            "A local Docker socket is required for this dev script."
        )
    return [
        "docker",
        "compose",
        "--project-directory",
        str(ROOT),
        "--file",
        str(ROOT / "docker-compose.yml"),
        "--project-name",
        ROOT.name,
    ]


def psql(compose, sql):
    """
    Send SQL over stdin to the fixed local development database.
    """
    return command(
        [
            *compose,
            "exec",
            "-T",
            "postgres",
            "psql",
            "-X",
            "-qAt",
            "--set",
            "ON_ERROR_STOP=1",
            "--username",
            "postgres",
            "--dbname",
            "litigant_portal",
        ],
        input_text=sql,
    )


def install_sql(bundle, fingerprint, recreate_empty=False):
    """
    Serialize installers and fail closed on an unrecognized existing schema.
    """
    recreate = ""
    if recreate_empty:
        tables = sorted(
            re.findall(r"CREATE TABLE public\.(agent_\w+)", bundle)
        )
        names = ",".join(f"'{name}'" for name in tables)
        previous_names = ",".join(
            f"'{name}'" for name in sorted([*tables, *REMOVED_TABLES])
        )
        recreate = f"""
DO $recreate$
DECLARE t record; has_rows boolean; object_list text; expected_tables text[]; installed text;
BEGIN
    IF to_regclass('public.agent_user') IS NULL THEN RETURN; END IF;
    installed := coalesce(obj_description('public.agent_user'::regclass, 'pg_class'), '');
    IF installed = '{PREVIOUS_INSTALLATION}' THEN
        expected_tables := ARRAY[{previous_names}]::text[];
    ELSIF installed LIKE '{MARKER}%' THEN
        expected_tables := ARRAY[{names}]::text[];
    ELSE
        RAISE EXCEPTION 'Refusing to rebuild an unrecognized schema';
    END IF;
    IF (SELECT array_agg(tablename::text ORDER BY tablename) FROM pg_tables
        WHERE schemaname = 'public' AND tablename LIKE 'agent\\_%' ESCAPE '\\')
        IS DISTINCT FROM expected_tables THEN
        RAISE EXCEPTION 'Unexpected agent tables; refusing to rebuild';
    END IF;
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename = ANY(expected_tables) ORDER BY tablename LOOP
        EXECUTE format('LOCK TABLE public.%I IN ACCESS EXCLUSIVE MODE', t.tablename);
        EXECUTE format('SELECT EXISTS (SELECT FROM public.%I)', t.tablename) INTO has_rows;
        IF has_rows THEN RAISE EXCEPTION 'Agent tables contain data; empty rebuild refused'; END IF;
    END LOOP;
    SELECT string_agg(format('public.%I', tablename), ',') INTO object_list
        FROM pg_tables WHERE schemaname = 'public' AND tablename = ANY(expected_tables);
    EXECUTE 'DROP TABLE ' || object_list; -- No CASCADE: external dependencies stop the rebuild.
    SELECT string_agg(p.oid::regprocedure::text, ',') INTO object_list FROM pg_proc p
        WHERE p.pronamespace = 'public'::regnamespace AND p.proname = ANY(ARRAY[
            'agent_touch_updated_at','agent_guard_immutable','agent_validate_record',
            'agent_scope_allowed','agent_lookup_context','agent_source_allowed',
            'agent_private_candidates','agent_search_private','agent_get_private_source',
            'agent_corpus_candidates','agent_search_corpus','agent_get_corpus_source']);
    IF object_list IS NOT NULL THEN EXECUTE 'DROP FUNCTION ' || object_list; END IF;
END
$recreate$;
"""
    return f"""
BEGIN;
SET LOCAL lock_timeout = '10s';
SET LOCAL statement_timeout = '60s';
SELECT pg_advisory_xact_lock(173904, 1);
{recreate}
SELECT EXISTS (
    SELECT FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relname LIKE 'agent\\_%' ESCAPE '\\'
) AS already_installed \\gset
\\if :already_installed
DO $guard$
BEGIN
    IF obj_description(to_regclass('public.agent_user'), 'pg_class')
       IS DISTINCT FROM '{MARKER}{fingerprint}' THEN
        RAISE EXCEPTION 'Existing agent objects differ from this script. No changes made; review the schema difference explicitly.';
    END IF;
END
$guard$;
\\else
{bundle}
COMMENT ON TABLE public.agent_user IS '{MARKER}{fingerprint}';
\\endif
COMMIT;
"""


def main():
    """
    Inspect, display, or install without touching migrations or seed data.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--sql", action="store_true")
    mode.add_argument(
        "--recreate-empty",
        action="store_true",
        help="Explicitly replace this script's installation only if every agent table is empty.",
    )
    args = parser.parse_args()
    if args.sql:
        print("\n\n".join((SQL_DIR / name).read_text() for name in SQL_FILES))
        return
    compose = compose_command()
    if not args.status:
        command([*compose, "up", "-d", "--no-deps", "--wait", "postgres"])
    if args.status:
        print(
            psql(
                compose,
                """
SELECT json_build_object(
    'database', current_database(),
    'postgres_version', current_setting('server_version'),
    'vector_version', (SELECT extversion FROM pg_extension WHERE extname = 'vector'),
    'agent_tables', (SELECT count(*) FROM pg_tables WHERE schemaname = 'public'
        AND tablename LIKE 'agent\\_%' ESCAPE '\\'),
    'agent_functions', (SELECT count(*) FROM pg_proc WHERE pronamespace = 'public'::regnamespace
        AND proname LIKE 'agent\\_%' ESCAPE '\\'),
    'installation', obj_description(to_regclass('public.agent_user'), 'pg_class')
);
""",
            )
        )
        return
    bundle = "\n\n".join((SQL_DIR / name).read_text() for name in SQL_FILES)
    fingerprint = hashlib.sha256(bundle.encode()).hexdigest()
    sql = install_sql(bundle, fingerprint, args.recreate_empty)
    output = psql(compose, sql)
    if output:
        print(output)
    print("Local agent schema installed.")
    print("Database: litigant_portal; schema: public; table prefix: agent_.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, OSError) as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        sys.exit(1)
