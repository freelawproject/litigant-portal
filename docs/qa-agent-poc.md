# Agent database PoC on QA

The EKS QA action is unchanged, including its tests, build, migration pod, and web rollout.
`manage migrate --noinput` installs the experimental agent schema through
migration `0019_agent_schema`. Each new web pod's existing
`manage sync_corpus --strict` startup command publishes real agent corpus data.
Publication failures stop startup and fail the rollout.

## Database and credentials

The database needs PostgreSQL with pgvector and a migration login permitted to
install the extension and create the three non-login agent permission groups.
The SQL snapshot is packaged with the application. An existing manual installation
is adopted only when its fingerprint and table/function inventory match.
Migration reversal retains agent tables and data; reapplying recognizes them.
Future schema changes need subsequent migrations.

For this PoC, application settings default `LP_AGENT_DEV_ENABLED` and
`LP_AGENT_USE_DJANGO_DB` to true when the deployment supplies `DEPLOYMENT_ENV=qa`.
Explicit values for either setting override these defaults. The shared option
opens independent agent connections using Django's configured database credentials
and bypasses restricted-lookup login validation. There are no extra passwords to
provision. Local Compose enables the same option.

Both application defaults are false outside QA; enabling shared credentials in
production raises a configuration error when the agent opens a connection. To
restore dedicated credentials, set `LP_AGENT_USE_DJANGO_DB=false` and configure
`LP_AGENT_WRITER_DSN` and `LP_AGENT_LOOKUP_DSN` as described in the
[agent README](../lp_agent/README.md). Developer page permissions still apply.

## Published material

The publisher reads `litigant_portal/corpus/`, the court/topic prompt files, and
the agent's current base prompt. With no `CORPUS_COURT` restriction, it publishes:

- North Dakota adult name change: standard and waiver procedures.
- Franklin County, Ohio eviction: tenant and landlord procedures.
- Five prompts, 31 fact definitions, 20 preparation phases, and 54 phase/fact links.
- Form mappings and text extracted from the eight repository PDFs, stored in
  procedure metadata using the existing agent representation.

It does not load `scripts/agent_eval`, benchmark snapshots, fictional evaluation
scopes, or sample users, conversations, or facts. It creates no S3 objects or
embeddings. The normal corpus command also refreshes the existing Django forms.

Imports are serialized and transactional within the agent catalog. Unchanged
imports retain IDs, versions, and timestamps. Changes append immutable revisions,
preserving material already pinned to runs. Strict sync disables or withdraws
removed imported material without deleting agent history. `--court` and
`CORPUS_COURT` select the same court as the normal Django corpus sync.

QA deploys preserve existing agent history. A local reset is a separate operation:
back up the local database, pause application writes, empty only the known agent
tables, and rerun migrations and corpus sync. Django accounts and unrelated
application data remain intact.
