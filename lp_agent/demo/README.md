# Local agent demonstration

All implementation and demo helpers for this change live in `lp_agent/`.
The existing `PortalAgent` constructor and its `create_environment` call are
unchanged. The factory reads the configured default database parameters lazily
and opens its own async psycopg connections. Agent records use the existing
database adapter and restricted search functions.

The experimental [SQL bundle](../tests/fixtures/agent_db/) must already be
installed in the local database. Seed the repository's existing material:

```sh
docker compose exec -T django python -m lp_agent.demo.seed --settings litigant_portal.settings --resource-root /app/litigant_portal
```

This requires `DEBUG=true` and `DEPLOYMENT_ENV=dev`. Seeding is repeatable; a
changed published procedure or prompt must be revised explicitly. No automatic
schema installation, replacement of published content, or Django management
command is added.

The unchanged development page supports independent submissions. Continue a
preparation conversation with the existing Python `conversation_id` argument,
as shown in the [package README](../README.md#calling-the-agent). Select a native
Bedrock model. Procedure choice happens through conversation; no constructor
argument or page selector is required.

For a repeatable live check using synthetic facts:

```sh
docker compose exec -T django python -m lp_agent.demo.smoke --settings litigant_portal.settings --resource-root /app/litigant_portal --compare --output /app/lp_agent/demo/live_results.json
```

This makes real provider calls and creates synthetic conversations in the local
agent database. It exercises all four preparation procedures, then asks five
North Dakota questions with the corpus and, with `--compare`, the same configured
model without corpus or tools. It exits unsuccessfully if a walkthrough does not
reach its handoff. The saved output contains messages, outcomes, and progress;
provider reasoning and credentials are excluded.

## Recorded observations

The [live observations](live_results.json) record the model and UTC timestamp.
All four procedures reached the preparation handoff: standard name change in
four turns, publication waiver in five, tenant eviction in four, and landlord
eviction in four. These were synthetic bulk-fact walkthroughs followed by
separate acknowledgements, not a usability evaluation of the individual questions.

All five corpus questions completed without selecting a guided procedure. The
filing-fee answer matched the supplied $160 corpus value; the comparison model
answered $80. When asked how recent a background check must be, the grounded
answer identified the missing corpus requirement and referred to the county
clerk, while the comparison supplied a 30-day rule. The same-day-service question
also produced an explicit lack-of-evidence response with a court contact. These
are observations from the saved calls, not an independent legal review or a
benchmark acceptance claim.

Facts require exact evidence from the current message and schema-valid values.
Corrections preserve provenance and reopen review. Optional phases and final
confirmation need separate replies. Progress and tool effects are committed
with their audit records; cancelled or failed response items are excluded from
later model history. Preparation completion provides existing resource links.
It does not fill, submit, or file forms. Judge and retry hooks report `skipped`.

## Validation boundary

The package tests cover the actual unchanged `PortalAgent` call, scoped corpus,
conversation ownership, concurrent runs, transaction rollback, native reasoning
history, fact evidence, corrections, confirmation, form citations, and all four
preparation paths. Production package types are checked with:

```sh
docker compose exec -T django .tox/py313/bin/mypy --disable-error-code import-untyped --exclude '/tests/' lp_agent
```

The import warning exclusion accounts for third-party packages whose typing
stubs are not installed; it does not disable checking the agent code.

The full project suite still has three failures in the unchanged development
page stream tests. Those tests do not provision the experimental agent tables
and assume the earlier memory-only environment and immediate raw text deltas.
The preparation flow buffers model text until its response checks finish.
Updating the page and its integration tests is deferred to the page PR. No
page, host wrapper, settings, or project test files were modified here.
