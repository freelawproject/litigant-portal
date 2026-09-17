# Experimental agent schema fixtures

These SQL files define the experimental `agent_` schema used by the PostgreSQL
surface tests. They remain separate from application migrations and seed data
pending team review.

The database test fixture applies these files in order, in one transaction:

1. `agent_tables.sql`: tables, indexes, and basic constraints.
2. `agent_constraints.sql`: foreign keys, validation, and integrity triggers.
3. `agent_search.sql`: stored lookup functions and restricted database roles.

The tests use a temporary database on the configured PostgreSQL server and drop
it during teardown. The existing Docker and CI PostgreSQL services provide
pgvector and administrator access for database and role creation. SQL setup
creates the three non-login agent roles if absent and validates existing roles.
Those permission groups are shared with local development and retained after
testing. Tests create separate writer and lookup logins with temporary
credentials, connect as those logins, and drop them during teardown.

Run the tests through the project configuration with `make test` or
`make pre-commit`. No schema installation is needed before running the tests.

For a local experiment, the temporary installer reads this same SQL bundle:

```sh
python3 lp_agent/tests/fixtures/agent_db/setup_agent_db.py
python3 lp_agent/tests/fixtures/agent_db/setup_agent_db.py --status
```

It starts only the local Compose PostgreSQL service and installs into
`litigant_portal.public`. An unchanged rerun keeps existing data; a changed
bundle is rejected. `--recreate-empty` only replaces a recognized installation
when every agent table is empty. It refuses unknown objects and external
dependencies and uses no cascading drops. Migrations and seed data are separate.

The installer creates no login credentials. For local integration, open an
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
