# Litigant portal agent contract

This package owns the agent contract, engagement behavior, and execution.
The current PR2 review step supports one fully scoped Direct model response,
with text/status/outcome events and instance-local stores. The development page
calls real Bedrock through the package's optional provider adapter.

Each submission currently creates an independent conversation. Continuation,
durable recovery, discovery, tools, queue, and steer are subsequent review steps;
unsupported operations raise explicitly. `get_run()` and `serve_mcp()` remain
unimplemented. Workers follows in PR3.

| Part                    | Responsibility                                                                 |
| ----------------------- | ------------------------------------------------------------------------------ |
| `main.py`               | Public `LPAgent` facade and immutable execution configuration                  |
| `types.py`              | Serializable requests, events, outcomes, questions, and adapter data           |
| `interfaces.py`         | Async run-handle and host-service contracts                                    |
| `environment.py`        | Live services and verified context, separate from serialized data              |
| `errors.py`             | Validation, access, and busy errors before acceptance                          |
| `flows/`                | Scope preparation, model steps, prompts, state transitions, and outcomes       |
| `runtimes/`             | Admission, owned Direct tasks, shutdown, and synchronous event streaming       |
| `adapters/`             | Bedrock, supplied catalogue, environment assembly, and temporary memory stores |
| `litigant_portal.agent` | Thin identity translation and options forwarding for the Django caller         |

Package implementations never import `litigant_portal`. Optional framework
integrations belong inside `lp_agent` and accept caller-supplied bindings or data.
The future Django storage integration will own its models and migrations, with
separate conversation/message records; it will not reuse legacy chat storage.
The existing agent and its provider implementation remain independent.

## Calling the agent

For the currently connected Direct path, supply a complete court/topic scope and
close the agent when its owning request ends:

```python
from lp_agent import LPAgent


async def first_response(environment):
    async with LPAgent(environment=environment) as agent:
        run = await agent.run(message="Hello")
        async for event in run.events():
            print(event.model_dump_json())
        return await run.result()
```

`aclose()` waits for submission preparation already in progress to finish
acceptance, then cancels and joins the accepted Direct tasks. Admission and
shutdown share one lock, so no work can be accepted after shutdown completes.
Repeated close is harmless. A terminal state commit already in progress finishes
before shutdown returns.

Cancellation closes unfinished model streams. The current handle supports one
live event consumer; `result()` also works without
observing events. A model stream must close cleanly and emit `ModelFinished` to
distinguish completion from truncation. Provider exceptions become safe failures.

### Supplied configuration

Keep the regular `LPAgent(environment=..., ...)` constructor when supplying your
own services. For the current Bedrock development setup, the package also provides
`lp_agent.adapters.environment.create_environment`:

```python
from lp_agent import LPAgent
from lp_agent.adapters.environment import create_environment


def configured_agent(identity_id, load_model, load_api_key, load_catalog):
    return LPAgent(
        environment=create_environment(
            identity_id=identity_id,
            court="court-id",
            topic="topic-id",
            model=load_model,
            api_key=load_api_key,
            catalog=load_catalog,
        )
    )
```

Each factory option accepts a value or a synchronous zero-argument callback.
Callbacks run once during initialization and may perform I/O. Their resolved
values are validated; callbacks are not retained or invoked during a run.
Async callbacks are rejected. The factory does not read Django settings, query
application models, or discover credentials from environment variables.

The catalogue is a tuple of `lp_agent.adapters.catalog.Court` values. Each court
has `choice_id`, `label`, and a tuple of topic `Choice` values. Equivalent plain
dictionaries are also validated by the factory. IDs must be unique within their
court or catalogue. The caller supplies only permitted choices.

The adapter exports `lp_agent.adapters.bedrock.MODEL_CHOICES` for selectors and
requires an explicit API key. The key stays in live adapter configuration, outside
serializable run configuration, checkpoints, and events. LiteLLM loads only when
the Bedrock adapter executes a request.

`PortalAgent(identity=..., model=..., api_key=..., catalog=..., ...)` converts
the verified Django identity's primary key to an opaque string and forwards these
options to the factory. It inherits agent methods and defaults to `Workers`, which
is still unimplemented. The development view selects `Direct`, supplies the
permitted catalogue and server credentials, and uses the Site assistant model as
the page's default. Authentication and HTTP input validation remain in Django.

### Synchronous event streaming

`agent.stream(...)` takes the same submission arguments as `run()` and returns a
synchronous iterator of newline-delimited JSON (NDJSON). It exclusively owns an
unused agent instance and one event loop. Use `run()` in async code; do not mix
the two interfaces on one instance.

```python
with agent.stream(message="Hello") as events:
    for line in events:
        send_to_client(line)
```

Exhaustion, errors, or `close()` release the run, model stream, loop, and agent.
Closing before the first iteration also closes the agent. When stopping early,
use the context manager or explicitly close the iterator. The closed agent cannot
be reused. Django can pass this iterator directly to `StreamingHttpResponse`,
which registers its `close()` method for response cleanup. Django owns the
response and headers; the package owns event encoding and execution cleanup.

Accepted runs emit the existing typed status/text/outcome envelopes. Submission
failures inside the iterator use `{"error": "safe message"}`. Invalid submission
data is rejected before constructing the iterator.

## Remaining PR2 contract

The following describes the complete interface that PR2 will implement:

```python
from lp_agent import LPAgent, RunLimits
from lp_agent.types import ChoiceAnswer


async def converse(environment, choose):
    async with LPAgent(
        environment=environment,
        runtime="Direct",
        interrupt_behavior="reject",
        limits=RunLimits(),
    ) as agent:
        run = await agent.run(message="I need help", attachment_ids=())

        async for event in run.events():
            if event.payload.type == "question":
                # The host presents the choices and obtains a user's selection.
                selected_choice_id = await choose(event.payload.question)
                answer = ChoiceAnswer(choice_id=selected_choice_id)
                await run.respond(event.payload.question.question_id, answer)

        return await run.result()
```

`run(message=..., conversation_id=None, attachment_ids=())` creates a conversation
when its identifier is omitted. Otherwise it continues an authorized conversation.
Identifiers are opaque nonempty strings; adapt host UUIDs with `str(id)`.
Blank messages are invalid; valid messages retain their whitespace and content.

`RunHandle` is a protocol, with read-only `run_id` and `conversation_id` properties:

| Operation                                           | Contract                                                                    |
| --------------------------------------------------- | --------------------------------------------------------------------------- |
| `await run.status()`                                | Read saved state, including a pending question                              |
| `run.events()`                                      | Iterate typed live events without awaiting the iterator itself              |
| `await run.result()`                                | Wait for a completed, failed, or cancelled outcome                          |
| `await run.respond(question_id, ChoiceAnswer(...))` | Validate the pending question and selected choice, then resume the same run |
| `await run.cancel()`                                | Request cancellation; status/result report acknowledgement                  |
| `await agent.get_run(run_id)`                       | Recover an authorized handle after reconstructing the agent                 |

Waiting for input is nonterminal. Reconnecting callers recover saved status,
questions, and final outcomes; there is initially no public event replay cursor.
Events include an attempt number so consumers can distinguish restarted output.
The host owns the HTTP response and browser rendering. The package owns the
NDJSON bridge, live event buffering, and execution lifetime.

`AgentValidationError`, `AgentAccessError`, and `AgentBusyError` reject invalid or
unauthorized submissions and replies before acceptance. After acceptance,
execution failures produce a `FailedOutcome` containing a caller-safe `PublicError`.
Constructing data models directly uses Pydantic's `ValidationError`.

## Scope and services

The host verifies both signed-in and anonymous identity and supplies an
`AccessContext(identity_id=...)`. This value asserts host verification; it does
not authenticate a caller. Service adapters enforce permissions on every operation.

`AgentEnvironment` contains that context, conversation/run stores, a scope catalog,
a scope factory, and `ScopeSelection(court=None, topic=None)`. The selection can
also supply either or both identifiers. Constructing this dataclass or `LPAgent`
does not invoke services. The optional environment factory does invoke any
supplied initialization callbacks, as described above.

Normal execution requires both court and topic. A later PR2 step will resolve
missing scope using fixed procedural questions and the host catalog, without a
model call. Discovery preserves the
original message and run ID while releasing execution resources between replies.
Once scope is complete, the factory binds a `ScopedEnvironment` with the same
identity, a full `Scope`, model access, and separate corpus/document searches.
The instance binds once and automatically continues the original message.

Search adapters return ranked `SearchHit` values with relevance and provenance.
They enforce bound identity/court/topic access and conversation attachment limits.
Relevance filtering and returned-context limits belong in procedural tool code;
actual ingestion and retrieval arrive in their planned later PRs.

Prompts, tools, and discovery belong to flows; runtimes decide how flows execute.
Provider clients, storage connections, and optional Django model access belong to
package adapters with caller-supplied configuration. Only contract models are
serialized with `model_dump_json()` and restored
with `model_validate_json()`; use Pydantic `TypeAdapter` for unions such as
`RunOutcome`. Service environments are never checkpoint or event payloads.

The version-1 `RunCheckpoint` envelope contains run/conversation identifiers and
JSON data. PR2 defines executor-state contents, accepted-input persistence, and
atomic checkpoint commits. Persisted work survives replacement of the agent object.

## Execution policy

Runtime and interruption policy are fixed at construction. `Direct` is the package
default; `Workers` is the portal default. `await agent.serve_mcp()` is a separate
unimplemented Model Context Protocol entry point, not a runtime selection.

| Interruption policy | New message during an active run                                    |
| ------------------- | ------------------------------------------------------------------- |
| `reject` (default)  | Raise a busy error                                                  |
| `queue`             | Create a queued run; add its message to history only when it starts |
| `steer`             | Preserve the input in order and return the active run's handle      |

Steering takes effect after the current model response or tool operation. Finish
tool A, mark remaining unstarted calls skipped, and let the model reconsider before
tool B. Cancellation is separate; a browser disconnect does not cancel worker work.

Defaults are 30 model steps, 300 active seconds, and two automatic worker restarts.
Budgets span recovery attempts and exclude queue time and waiting for human input.
Step/time limits must be positive; zero restarts disables automatic recovery.

## Checks

From the repository root, run `tox -e agent`. Its isolated environment installs only
Pydantic and pytest, disables plugin autoload, and requires neither Django nor a
database or provider credentials. With existing development dependencies, use:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -c lp_agent/pytest.ini lp_agent/tests
```

This configuration excludes `tests/providers/`. With LiteLLM and pytest installed,
exercise provider normalization and credential forwarding without initializing
Django:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -c lp_agent/pytest.ini lp_agent/tests/providers
```

The regular project suite includes both groups plus the Django wrapper and HTTP
tests. Core checks cover blocked host/provider imports, configuration and callback
validation, serialization, Direct flow behavior, submission/shutdown races, and
stream cleanup. Provider tests use synthetic SDK responses and make no live calls.
