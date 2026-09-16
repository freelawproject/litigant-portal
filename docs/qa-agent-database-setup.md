# One-time QA agent role setup

The temporary agent PoC **does not require pgvector**. Its remaining database
prerequisites are permission groups and permission to transfer search-function
ownership. The GitHub workflow and application credentials stay unchanged.

An administrator with role-management and schema-grant permissions should run
this in the **QA application database**, using its existing `POSTGRES_USER` as
`qa_app_role`. The application login needs its usual inherited role permissions
and permission to create objects in `public`.

```sql
\set ON_ERROR_STOP on
\set qa_app_role 'replace-with-the-existing-QA-application-login'

DO $roles$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'agent_dev_crud', 'agent_dev_lookup', 'agent_dev_reader'
    ] LOOP
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('CREATE ROLE %I NOLOGIN', role_name);
        END IF;
    END LOOP;
END
$roles$;

GRANT USAGE, CREATE ON SCHEMA public TO agent_dev_reader;
GRANT agent_dev_reader, agent_dev_crud TO :"qa_app_role";
```

Retry the normal QA deployment. After migration succeeds, remove the following
temporary grants **only if introduced by this setup**, preserving pre-existing
privileges:

```sql
REVOKE CREATE ON SCHEMA public FROM agent_dev_reader;
REVOKE agent_dev_reader FROM :"qa_app_role";
```

Keep the application's `agent_dev_crud` membership and the reader's schema
`USAGE`: these supply normal runtime access. A failed migration is atomic;
retrying does not require clearing tables or marking it as applied manually.

Fresh installation without pgvector is tested with a non-superuser login after
these role grants. Live RDS deployment verification remains pending.
