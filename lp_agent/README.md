# Litigant portal agent

`lp_agent` owns the agent interface, behavior, and execution. Call it through
`LPAgent` or the Django `PortalAgent` wrapper. It is separate from the existing
chat engine.

Direct execution supports one model response per submission, streamed as typed
status, text, and outcome events. Each submission creates an independent
conversation. The supplied Bedrock environment stores state in memory on that
instance; runs do not survive instance replacement or restart.

Conversation continuation, attachments, durable recovery, scope discovery, tools,
queue/steer, Workers, and Model Context Protocol (`serve_mcp()`) are unimplemented.
File-based corpus retrieval exists, but corpus content does not yet reach the
model.

The [current prompt](flows/prompts.py) is a development placeholder with basic
honesty guidance. Full legal-information boundaries, plain-language guidance,
and grounded content belong in these package-owned prompt layers under Court
and Topic Grounding and Safety Boundaries, before main-chat integration.

## Calling the agent

`LPAgent` defaults to Direct execution. Supply a host-verified identity ID, a model
from [`MODEL_CHOICES`](adapters/bedrock.py), and a server-held Bedrock API key.
Both court and topic are required to run. `resource_root` is the directory
containing `corpus/` (`litigant_portal/` in this checkout).

The supplied factory builds a Bedrock environment. For custom services, assemble
an [`AgentIdentity`](identity.py) from the [service contracts](interfaces.py).

```python
from lp_agent import LPAgent
from lp_agent.adapters.environment import create_environment


async def first_response(identity_id, model, api_key, resource_root):
    environment = create_environment(
        identity_id=identity_id,
        model=model,
        api_key=api_key,
        resource_root=resource_root,
        court="north-dakota",
        topic="adult-name-change",
    )
    async with LPAgent(environment=environment) as agent:
        run = await agent.run(message="Hello")
        async for event in run.events():
            print(event.model_dump_json())
        return await run.result()
```

A run supports one event consumer. `result()` returns a completed, failed, or
cancelled outcome and also works without consuming events. `await run.cancel()`
cancels the run. The async context manager, or `await agent.aclose()`, cancels and
joins outstanding runs when the owner exits.

For synchronous callers, give a fresh agent a configured environment.
`stream()` yields newline-delimited JSON (NDJSON) and owns that agent:

```python
def stream_response(environment):
    agent = LPAgent(environment=environment)
    with agent.stream(message="Hello") as events:
        for line in events:
            print(line, end="")
```

The stream closes the run, event loop, and agent on exhaustion or error. Use its
context manager or call `close()` when stopping early. The agent cannot then be
reused; use `run()` in async code and never mix the two interfaces on one instance.

Validation and access errors raise `AgentError` subclasses. Accepted model
failures return a `FailedOutcome`; errors caught inside `stream()` become
`{"error": "safe message"}` lines.

Checkpoint failures raise `AgentStorageError` with a fixed safe message from
async results, event iteration, cancellation, or agent closure. Stored state
may still be queued or running: a terminal outcome is published only after its
checkpoint is saved. Synchronous iteration encodes the safe error; explicit
closure can raise it after cleanup.

The Bedrock adapter ignores extra fields on recognized output items and content
parts, while retaining supported metadata. Unknown item types and malformed
known fields still fail, and other valid completed items remain in the
checkpoint. Public input contracts remain strict.

Operational warnings use standard Python logging. Ignored provider fields
produce one warning per response with the model and field count; checkpoint
failures include the run ID and state. These warnings omit prompts, response
content, unknown field names, credentials, and raw exception text. Broader
observability and restricted prompt/output auditing are separate work.

## Django development page

Follow the [repository quick start](../README.md#quick-start), then open
`/dev/agent/`. The page makes real Bedrock calls and requires:

- `LP_AGENT_DEV_ENABLED=true` (already enabled by local Docker Compose).
- A logged-in user with the `app.manage_developers` permission.
- `AWS_BEARER_TOKEN_BEDROCK` configured on the server.
- A selected model, court, and topic.

[`PortalAgent`](../litigant_portal/agent.py) takes the saved, host-verified
`request.identity` and the selected model/scope. It supplies the API key and
resource root from Django settings. **Pass `runtime="Direct"`**: the wrapper
defaults to Workers, which is unimplemented.

The [development view](../litigant_portal/app/views/agent.py) shows the full call
and passes `agent.stream(...)` to Django's `StreamingHttpResponse`. Django owns
authentication, input validation, and HTTP response headers.

A missing server Bedrock key returns HTTP 503 with a safe warning; invalid form
submissions return HTTP 400. Sending captures the message and clears the input
before streaming the response.

## Where things live

Package implementations never import `litigant_portal`. Flows own prompts and
model behavior; runtimes decide how flows execute.

| Part                                                           | Responsibility                                                                                       |
| -------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| [`main.py`](main.py)                                           | Public facade and execution configuration                                                            |
| [`types.py`](types.py)                                         | Serializable requests, model data, events, and outcomes                                              |
| [`interfaces.py`](interfaces.py), [`identity.py`](identity.py) | Run handles, service contracts, and verified context                                                 |
| [`errors.py`](errors.py)                                       | Caller-safe error contracts                                                                          |
| [`flows/`](flows/)                                             | Scope preparation, model steps, prompts, and outcomes                                                |
| [`runtimes/`](runtimes/)                                       | Direct tasks, event delivery, streaming, and shutdown                                                |
| [`adapters/`](adapters/)                                       | [Environment factory](adapters/environment.py), [Bedrock](adapters/bedrock.py), and temporary stores |
| [`corpus/`](corpus/)                                           | File retrieval and stubs for other retrieval backends                                                |
| [`utils/audit.py`](utils/audit.py)                             | Canonical instruction snapshots and fingerprints                                                     |

## Experimental database surfaces

Django models and migrations currently own the shared application and agent
schema. Existing web CRUD stays in Django services. The agent adapter retains
its SQL operations, and lookup functions and integrity triggers remain SQL
because they enforce database permissions, ownership, and atomic invariants.
The intended later home for custom application data is a shared `lp_database`
module; its implementation and ORM selection are outside this PR.

Existing application writes use `transaction.atomic()`. A write combining ORM
and SQL must use that same Django connection. Agent-only operations use
`db.transaction()` on their caller-owned psycopg connection. Separate Django
and psycopg connections do not share a transaction. Court-authoring methods
require the host-controlled `AccessContext.author` capability, defaulting false.

The database adapters are available for integration; the supplied environment
still uses memory stores. See the [schema installation](tests/fixtures/agent_db/)
for local installation and separate writer/lookup login credentials.

Create connections inside the process and event loop using them, including
inside a worker after it starts. Give independent concurrent work separate
connections. The context managers configure dictionary rows and autocommit and
close on exit. `lookup_connection()` also rejects a privileged session login,
extra role memberships, and agent-table/internal-function privileges.

With host-verified access and a prepared run, group related writes with their
checkpoint. Let errors escape the transaction block so all its writes roll back:

```python
from lp_agent.adapters.connections import agent_connection, lookup_connection
from lp_agent.adapters.db import AgentDatabase
from lp_agent.tools.agent_search import AgentSearch

async with agent_connection(writer_dsn) as connection:
    db = AgentDatabase(connection, access)
    async with db.transaction():
        await db.append_item(
            checkpoint.conversation_id,
            key=item_key,
            payload=item_payload,
            run_id=checkpoint.run_id,
        )
        saved = await db.commit_checkpoint(checkpoint, status, outcome)
    checkpoint = saved

async with lookup_connection(lookup_dsn) as connection:
    search = AgentSearch(
        connection,
        access=access,
        run_id=checkpoint.run_id,
        host_policy=current_host_policy,
    )
    hits = await search.search(query)
```

`RunStore.commit_checkpoint()` returns a detached saved checkpoint. Carry its
`storage_version` into the next write; database checkpoint reads also return it.
An initial database write uses `None`. `Engagement` carries the returned version
automatically. Stores without optimistic versioning can return `None` for that
field. A stale version is rejected; reloading just before writing would bypass
the protection against stale work.

`get_database_corpus()` delegates scope checks and initial revision selection to
`AgentDatabase.pin_run_context()`, then returns available pinned material for a
consuming flow. Runtime retrieval wiring and live model grounding remain separate.

## Checks

From the repository root, run the isolated core checks:

```sh
tox -e agent
```

These cover contracts, Direct execution, and cleanup without Django, a database,
or provider credentials. Default `tox` and `make test` also run this environment.

With LiteLLM and pytest installed, run the provider checks separately:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -c lp_agent/pytest.ini lp_agent/tests/providers/test_bedrock.py
```

Provider checks use controlled responses and make no live model calls. The full
project suite also covers the Django wrapper and HTTP integration.

Database surface tests run through the project configuration in `make test` and
`make pre-commit`. To run just those tests with the Docker stack running:

```sh
docker compose exec -T django tox -e py313 -- -c pyproject.toml lp_agent/tests/providers/test_database.py -q
```

The tests create a temporary database and dedicated login roles on the configured
PostgreSQL service, install the [application migrations](tests/fixtures/agent_db/),
and drop the database and logins during teardown. Setup errors fail the tests.
No local installation of the agent schema is required. `tox -e fast` excludes
PostgreSQL cases while retaining argument-validation coverage.
