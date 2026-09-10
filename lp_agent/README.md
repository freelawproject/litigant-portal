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

## Checks

From the repository root, run the isolated core checks:

```sh
tox -e agent
```

These cover contracts, Direct execution, and cleanup without Django, a database,
or provider credentials. Default `tox` and `make test` also run this environment.

With LiteLLM and pytest installed, run the provider checks separately:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -c lp_agent/pytest.ini lp_agent/tests/providers
```

Provider checks use controlled responses and make no live model calls. The full
project suite also covers the Django wrapper and HTTP integration.
