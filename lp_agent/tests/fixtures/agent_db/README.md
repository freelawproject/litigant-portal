# Agent database installation

Django models and migrations own the approved shared schema. Migration `0019`
adds the model fields and tables; `0020` contains the PostgreSQL-specific columns,
indexes, constraints, triggers, functions, and grants as inline `RunSQL`.
The specialized `vector` and `tsvector` columns are SQL-managed, not ORM fields.
Tests inspect these objects as well as checking model/migration consistency.
There is no separate fixture schema to maintain or install.

Install with the application's normal `manage migrate` command. These migrations
assume a fresh database, not an existing experimental `agent_` installation.
The existing corpus command remains the importer for the existing application
corpus. This PR adds no agent prompt or document publisher.

## Local and test roles

Server roles are provisioned separately from migrations. Docker and CI currently
use administrator PostgreSQL accounts; database tests explicitly provision the
three unprivileged, non-login permission groups below. They create temporary
writer and lookup logins, install the real migrations in a temporary database,
and remove that database and those logins afterward. Permission groups remain
server-level resources shared with local development.

For local agent database use, an administrator creates these groups before
running migrations, if they do not already exist:

```sql
CREATE ROLE agent_dev_crud NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE agent_dev_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE agent_dev_lookup NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
```

A non-superuser migration owner needs membership in `agent_dev_reader` to assign
ownership of the security-definer lookup functions. Infrastructure must also
install the `vector` extension before migrations if that owner cannot install
extensions. Migrations require no `CREATEROLE` permission. They validate existing
group attributes and apply grants to explicitly named shared/agent objects;
framework tables are excluded. With no agent groups provisioned, the schema
installs without enabling separate writer or lookup access. Public function
execution is revoked in either case.

Create separate login credentials administratively and set passwords
interactively, rather than putting passwords in committed commands:

```sql
CREATE ROLE agent_local_writer LOGIN IN ROLE agent_dev_crud;
CREATE ROLE agent_local_lookup LOGIN IN ROLE agent_dev_lookup;
\password agent_local_writer
\password agent_local_lookup
```

Pass their DSNs to `agent_connection()` and `lookup_connection()`. The lookup
login must inherit only `agent_dev_lookup`, lack schema-creation privileges,
and have no direct access to the shared tables or internal routines. Using
`SET ROLE` on an administrator connection is not a restricted lookup login.

## Production ownership

FLP infrastructure owns extension installation, migration-role memberships,
permission groups, login provisioning, and credential rotation. DSNs belong in
the deployment's existing secret mechanism; trusted host code supplies them to
the connection factories. This PR introduces no deployment wiring, new settings,
or environment-specific credential exceptions.

Court authoring additionally requires `AccessContext.author=True`, set only by
host code after its permission checks. Ordinary contexts default to false.
Separate author/writer database credentials remain infrastructure follow-up;
the current writer role can perform trusted application writes.

Embedding storage remains dimension-flexible. Select the embedding model,
dimensions, and vector index together when implementing vector retrieval.
Full-text query/index optimization and corpus-load limits are also deferred;
this PR preserves the existing lookup execution strategy.
