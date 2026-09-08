# Litigant portal agent contract

PR1 establishes a framework-independent Python package and its public contract.
It validates configuration and data. `run()`, `get_run()`, and `serve_mcp()`
raise `NotImplementedError`; they do not accept work or invoke adapters yet.
Direct execution and Django adapters follow in PR2; Workers follows in PR3.

| Part                    | Responsibility                                                       |
| ----------------------- | -------------------------------------------------------------------- |
| `main.py`               | Public `LPAgent` facade and immutable execution configuration        |
| `types.py`              | Serializable requests, events, outcomes, questions, and adapter data |
| `interfaces.py`         | Async run-handle and host-service contracts                          |
| `environment.py`        | Live services and verified context, separate from serialized data    |
| `errors.py`             | Validation, access, and busy errors before acceptance                |
| `litigant_portal.agent` | Host constructor and portal defaults                                 |

## Calling the agent

The following describes the interface that PR2 will implement:

```python
from lp_agent import LPAgent, RunLimits
from lp_agent.types import ChoiceAnswer


async def converse(environment, choose):
    agent = LPAgent(
        environment=environment,
        runtime="Direct",
        interrupt_behavior="reject",
        limits=RunLimits(),
    )
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
The host owns HTTP framing, browser rendering, and live-stream buffering.

`AgentValidationError`, `AgentAccessError`, and `AgentBusyError` reject invalid or
unauthorized submissions and replies before acceptance. After acceptance,
execution failures produce a `FailedOutcome` containing a caller-safe `PublicError`.
Constructing data models directly uses Pydantic's `ValidationError`.

## Scope and services

The host verifies both signed-in and anonymous identity and supplies an
`AccessContext(identity_id=...)`. This value asserts host verification; it does
not authenticate a caller. Host adapters enforce permissions on every operation.

`AgentEnvironment` contains that context, conversation/run stores, a scope catalog,
a scope factory, and `ScopeSelection(court=None, topic=None)`. The selection can
also supply either or both identifiers. No services are called during construction.

Normal execution requires both court and topic. Missing scope uses fixed procedural
questions and the host catalog, without a model call. Discovery preserves the
original message and run ID while releasing execution resources between replies.
Once scope is complete, the factory binds a `ScopedEnvironment` with the same
identity, a full `Scope`, model access, and separate corpus/document searches.
The instance binds once and automatically continues the original message.

Search adapters return ranked `SearchHit` values with relevance and provenance.
They enforce bound identity/court/topic access and conversation attachment limits.
Relevance filtering and returned-context limits belong in procedural tool code;
actual ingestion and retrieval arrive in their planned later PRs.

Prompts, tools, discovery, and execution policy belong to `lp_agent`. Django model
access, provider clients, storage connections, and credentials stay behind host
adapters. Only contract models are serialized with `model_dump_json()` and restored
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

`PortalAgent(identity=..., court=None, topic=None, runtime="Workers", ...)` declares
the host entry point now. It validates independent options and explicitly fails
construction until PR2 supplies Django environment wiring. It inherits agent methods.

## Checks

From the repository root, run `tox -e agent`. Its isolated environment installs only
Pydantic and pytest, disables plugin autoload, and requires neither Django nor a
database or provider credentials. With existing development dependencies, use:

```sh
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -c lp_agent/pytest.ini lp_agent/tests
```

The regular project suite also discovers these tests. Contract tests verify imports,
validation, serialization, and explicit placeholders; runtime behavior is tested
when implemented in PR2 and PR3.
