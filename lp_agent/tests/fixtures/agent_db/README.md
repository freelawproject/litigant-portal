# Experimental agent schema and database fixtures

The frozen SQL in
[`litigant_portal/app/migrations/agent_sql_0019/`](../../../../litigant_portal/app/migrations/agent_sql_0019/)
defines the experimental `agent_` schema. Django migration `0019_agent_schema`
installs it; the PostgreSQL surface tests and legacy local installer read the
same bundle. Keep it immutable and use subsequent migrations for schema changes.
Migration `0020_defer_agent_vectors` upgrades installations of the earlier
pre-release snapshot, which included unused pgvector storage.

The database test fixture applies these files in order, in one transaction:

1. `agent_tables.sql`: tables, indexes, and basic constraints.
2. `agent_constraints.sql`: foreign keys, validation, and integrity triggers.
3. `agent_search.sql`: stored lookup functions and restricted database roles.

The tests use a temporary database on the configured PostgreSQL server and drop
it during teardown. The schema does not require pgvector. Docker and CI provide
administrator access for database and role creation, plus pgvector availability
for the separate legacy-upgrade tests. SQL setup
creates the three non-login agent roles if absent and validates existing roles.
Those permission groups are shared with local development and retained after
testing. Tests create separate writer and lookup logins with temporary
credentials, connect as those logins, and drop them during teardown.

Run the tests through the project configuration with `make test` or
`make pre-commit`. No schema installation is needed before running the tests.

Normal local and QA startup runs `manage migrate --noinput` and
`manage sync_corpus --strict`, which also publishes the real agent corpus.
The [QA PoC guide](../../../../docs/qa-agent-poc.md) describes credentials and data.

The legacy installer remains available for an isolated local experiment and
read-only inspection:

```sh
python3 lp_agent/tests/fixtures/agent_db/setup_agent_db.py
python3 lp_agent/tests/fixtures/agent_db/setup_agent_db.py --status
```

It starts only the local Compose PostgreSQL service and installs into
`litigant_portal.public`. An unchanged rerun keeps existing data; a changed
bundle is rejected. `--recreate-empty` only replaces a recognized installation
when every agent table is empty. It refuses unknown objects and external
dependencies and uses no cascading drops. Do not use its rebuild option on a
database already managed by migration `0019`; use Django migrations there.

The shared dev/QA database option needs no additional login credentials. To test
the dedicated-login path with `LP_AGENT_USE_DJANGO_DB=false`, open an
administrator session with `docker compose exec postgres psql -U postgres -d
litigant_portal`, then create separate logins and set their passwords interactively:

```sql
CREATE ROLE agent_local_writer LOGIN IN ROLE agent_dev_crud;
CREATE ROLE agent_local_lookup LOGIN IN ROLE agent_dev_lookup;
\password agent_local_writer
\password agent_local_lookup
```

Supply their connection strings to `agent_connection()` and `lookup_connection()`
respectively. The lookup login must inherit only `agent_dev_lookup`, have no
direct agent-table or internal-function privileges, and have no schema-creation
privilege. A privileged session using `SET ROLE` does not meet that contract.
