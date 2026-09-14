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
Those roles are shared with local development and are retained after testing.

Run the tests through the project configuration with `make test` or
`make pre-commit`. The local development installer reads this same SQL bundle.
