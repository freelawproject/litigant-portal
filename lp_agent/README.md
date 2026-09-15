# Litigant portal agent

`lp_agent` owns the experimental agent interface, behavior, and execution.
The Django [`PortalAgent`](../litigant_portal/agent.py) wrapper supplies verified
identity and server configuration. The existing production chat is separate.

The database-backed [engagement flow](flows/new_engagement.py) loads a court's
configuration, topic guidance, procedures, and source material before answering.
It can answer a question without selecting a procedure, or guide preparation
while saving facts, their evidence, and progress in the existing `agent_` tables.

## Local development and demonstration

Follow the [demo setup and rehearsal](demo/README.md), then open `/dev/agent/`.
The page requires developer permission, `LP_AGENT_DEV_ENABLED=true`, a server-held
`BEDROCK_API_KEY`, and these server-side database settings:

- `LP_AGENT_WRITER_DSN`: a login inheriting `agent_dev_crud`.
- `LP_AGENT_LOOKUP_DSN`: a separate login inheriting only `agent_dev_lookup`.

The [experimental SQL fixture guide](tests/fixtures/agent_db/) explains setup.
The demo seeder loads all four existing repository procedures: North Dakota
standard and publication-waiver name changes, and Franklin County tenant and
landlord eviction preparation. It publishes new prompt revisions when their
text changes; it does not overwrite earlier revisions or published procedures.

Leave court or topic blank to choose through chat. Static numbered questions
select the court first, then its topic, without calling a model. The original
question is retained. All choices come from the enabled database catalog and
respect `CORPUS_COURT` when the deployment restricts access to one court.

The page retains the conversation across submissions and reloads through its
URL. It shows accepted messages, source links, preparation progress, and events.
Use **New conversation** to change bound scope, procedure, or assistant model.
A separate judge model is optional; the default is the assistant model.
GLM is available as a judge but cannot be the preparation assistant because its
adapter does not support native tools.

## Calling the agent

`LPAgent` defaults to Direct execution. `PortalAgent` currently defaults to the
unimplemented Workers runtime, so pass `runtime="Direct"` to that wrapper.
`resource_root` is the directory containing `corpus/` (`litigant_portal/` here).

```python
from lp_agent import LPAgent
from lp_agent.adapters.environment import create_environment


async def prepare(identity_id, model, api_key, resource_root):
    environment = create_environment(
        identity_id=identity_id,
        model=model,
        api_key=api_key,
        resource_root=resource_root,
        court="north-dakota",
        topic="adult-name-change",
    )
    async with LPAgent(environment=environment) as agent:
        first = await agent.run(message="What is the filing fee?")
        print(await first.result())
        following = await agent.run(
            message="Help me prepare a standard name change with publication.",
            conversation_id=first.conversation_id,
        )
        async for event in following.events():
            print(event.model_dump_json())
        return await following.result()
```

A run has one event consumer. `result()` also works without consuming events.
`await run.cancel()` cancels a run; exiting the agent's async context cancels and
joins outstanding work. Synchronous `agent.stream(message=..., conversation_id=...)`
yields NDJSON and owns its agent and event loop. Use it as a context manager or
close it explicitly when stopping early. Do not reuse that agent afterward.

## Answer checks and preparation

[PromptBuilder](flows/prompts.py) assembles instructions from published prompts
and one evidence/state snapshot. Court material is evidence, including its
citation IDs; embedded legacy UI instructions do not control the agent.
Missing evidence calls for an explicit gap and a supplied court contact.
Conflicting sources must be disclosed. Unrelated requests receive a legal-help
redirect, including requests presented as a demonstration.

The [judge](flows/judge.py) reviews each candidate against that same evidence and
saved state. It checks relevance, supported claims and citations, legal-help
boundaries, and whether claimed actions actually occurred. A source ID alone is
insufficient. Invalid IDs are also rejected deterministically.

There are at most three candidates: the original and two corrections. Correction
turns cannot call tools or repeat earlier effects. Status/tool events stream
immediately; answer text is released only after approval and its terminal
checkpoint commit. Judge errors, malformed verdicts, cancellation, or a third
rejection release no candidate. Rejected drafts remain in internal step audit,
outside the visible conversation and subsequent model history.

Facts require exact evidence from the user's current message and schema-valid
values. Changes retain provenance and reopen review. Optional phases and final
confirmation require a separate acknowledgement. Completion is a preparation
handoff with resource links, not filled forms, filing, or a court decision.
Automated review is not attorney review or a guarantee of legal correctness.

## Persistence and service boundaries

[`create_environment`](adapters/environment.py) keeps the public caller signature
and supplies lazy database services. Each run owns async connections through
[`agent_connection` and `lookup_connection`](adapters/connections.py). Independent
runs use independent connections. Lookup validates the session login; switching
a privileged login with `SET ROLE` does not satisfy the restricted-login contract.

[`AgentDatabase.transaction()`](adapters/db.py) groups effects, audit, and checkpoints.
`RunStore.commit_checkpoint()` returns a detached saved checkpoint; callers carry
its `storage_version` into the next write. Initial writes use `None`.
`Engagement` carries the returned version, restoring its prior version on rollback.
[`get_database_corpus()`](corpus/db_search.py) delegates selection and revision
pinning to `AgentDatabase.pin_run_context()` and loads the pinned published material.

Database failures never fall back to memory. Validation/access errors raise safe
`AgentError` subclasses; accepted model failures produce failed outcomes.
Checkpoint failures raise `AgentStorageError`, and a terminal outcome is published
only after persistence succeeds. NDJSON encodes safe errors without provider details.

For injected services, [`AgentIdentity`](identity.py) owns the optional typed
[preparation service](preparation.py). Omitting it retains the earlier isolated
single-response flow. [Core contracts](types.py), [runtime](runtimes/direct.py),
[tools](tools/engagement.py), and [HTTP integration](../litigant_portal/app/views/agent.py)
contain the detailed contracts.

## Validation and remaining work

Run `make pre-commit` for formatting, the full project suite, database fixtures,
and the isolated `tox -e agent` suite. Database tests create temporary databases
and dedicated logins from the committed SQL bundle; no local seed is needed.
They use controlled model responses. Type-check the production package with:

```sh
docker compose exec -T django .tox/py313/bin/mypy --disable-error-code import-untyped --exclude '/tests/' lp_agent
```

[Live observations and reproduction commands](demo/README.md) are separate from
controlled tests. They compare the same model with and without supplied corpus;
they are not a comparison against the complete ChatGPT.com product.
Attachments, form filling, filing, interrupted-run recovery, Workers, queue/steer,
and `serve_mcp()` remain unimplemented. Production chat migration and corpus
legal review remain separate work.
