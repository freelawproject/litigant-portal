# Litigant portal agent

`lp_agent` owns the agent interface, behavior, and execution. Call it through
`LPAgent` or the Django `PortalAgent` wrapper. It is separate from the existing
chat engine.

Direct execution streams the existing status, text, tool, question, and outcome
contracts. Preparation snapshots are typed internally and carried in
`ToolEvent.data`; the public event union is unchanged.

The existing `create_environment` factory assembles the database-backed
[preparation flow](flows/new_engagement.py) without additional caller arguments.
It loads published court/topic material before a procedure is selected, answers
questions from that material, and offers guided preparation. The model's
`select_procedure` tool records a choice grounded in the user's message; ambiguous
intent calls for clarification. Facts, evidence, corrections, and preparation
progress are persisted in the existing `agent_` tables.

Sequential submissions continue an owned conversation across agent instances
using the existing `conversation_id` argument. The selected procedure is stored
conversation state. Court, topic, and model remain fixed for a conversation.

Attachments, interrupted-run recovery, automatic scope discovery, queue/steer,
Workers, and Model Context Protocol (`serve_mcp()`) remain unimplemented. Judge
and correction-retry hooks are explicit logging stubs for the demo; they do not
provide semantic legal review or regenerate an answer.

## Calling the agent

`LPAgent` defaults to Direct execution. Supply a host-verified identity ID, a model
from [`MODEL_CHOICES`](adapters/bedrock.py), and a server-held Bedrock API key.
Both court and topic are required to run. `resource_root` is the directory
containing `corpus/` (`litigant_portal/` in this checkout).

The factory builds a Bedrock environment with lazy database services. It reads
Django's configured default database parameters only when a connection is needed,
then opens its own psycopg async connection using the existing development roles.
Each run owns a connection; status and store calls use separate short-lived
connections. No synchronous Django connection or ORM model is used for agent data.

For custom services, assemble an [`AgentIdentity`](identity.py) from the
[service contracts](interfaces.py). A scope can supply the typed
[preparation service](preparation.py); scopes without it retain the existing
single-response behavior. Database failures never fall back to memory.

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
        run = await agent.run(message="What is the filing fee?")
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

With the experimental [SQL bundle](tests/fixtures/agent_db/) already installed in
the local database, load the existing repository content through the package:

```sh
docker compose exec -T django python -m lp_agent.demo.seed --settings litigant_portal.settings --resource-root /app/litigant_portal
```

The schema is separate from Django migrations. Seeding requires `DEBUG=true` and
`DEPLOYMENT_ENV=dev`. It is repeatable and refuses to replace changed published
content. The returned phase count reports newly inserted phases.

The demo covers North Dakota adult name change (standard publication and
publication waiver) and Franklin County, Ohio eviction (tenant and landlord).
The seeder reads the existing procedures, variables, forms, public metadata, and
prompt fragments. It does not create new legal guidance. Use a native Bedrock
model; the translated GLM adapter rejects preparation tools.

The development page is unchanged and submits independent conversations. Its
multi-turn interaction and progress display are deferred to another PR. Exercise
continuation with the existing Python API:

```python
async with LPAgent(environment=environment) as agent:
    first = await agent.run(message="Please help me prepare a standard adult name change with publication.")
    print(await first.result())
    following = await agent.run(
        message="My current legal name is Alex Example.",
        conversation_id=first.conversation_id,
    )
    print(await following.result())
```

Required facts advance preparation deterministically. Optional steps and the
final summary require a separate acknowledgement; changed facts reopen review.
Completion means a preparation handoff with resource links. Saved facts are not
transferred into forms, and no form is filled or filed. Tool events include
`preparation_progress` snapshots and the explicitly skipped judge/retry check.

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

| Part                                                                                               | Responsibility                                                                 |
| -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| [`main.py`](main.py)                                                                               | Public facade and execution configuration                                      |
| [`types.py`](types.py)                                                                             | Serializable requests, model data, events, and outcomes                        |
| [`interfaces.py`](interfaces.py), [`identity.py`](identity.py), [`preparation.py`](preparation.py) | Run handles, scoped services, typed preparation material, and verified context |
| [`errors.py`](errors.py)                                                                           | Caller-safe error contracts                                                    |
| [`flows/`](flows/)                                                                                 | Scope preparation, model steps, prompts, and outcomes                          |
| [`runtimes/`](runtimes/)                                                                           | Direct tasks, event delivery, streaming, and shutdown                          |
| [`adapters/`](adapters/)                                                                           | Environment factory, Bedrock, memory stores, and lazy database sessions        |
| [`corpus/`](corpus/)                                                                               | File retrieval and published database corpus selection                         |
| [`tools/`](tools/)                                                                                 | Restricted search, evidence-backed fact updates, and acknowledgement           |
| [`demo/`](demo/)                                                                                   | Repeatable seeding of existing repository content                              |
| [`utils/audit.py`](utils/audit.py)                                                                 | Canonical instruction snapshots and fingerprints                               |

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
docker compose exec -T django tox -e py313 -- -c pyproject.toml lp_agent/tests/providers/test_database.py lp_agent/tests/providers/test_engagement.py -q
```

The tests create a temporary database on the configured PostgreSQL service,
install the [experimental SQL fixtures](tests/fixtures/agent_db/), and drop the
database during teardown. Setup errors fail the tests. No local installation of
the agent schema is required. `tox -e fast` excludes the PostgreSQL-marked cases
while retaining argument-validation coverage.

Type-check the production package (the project does not install Django, PyYAML,
or jsonschema typing stubs):

```sh
docker compose exec -T django .tox/py313/bin/mypy --disable-error-code import-untyped --exclude '/tests/' lp_agent
```
