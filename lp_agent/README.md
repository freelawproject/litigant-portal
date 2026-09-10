# Litigant portal agent contract

This package owns the agent contract, engagement behavior, and execution.
The current PR2 review step supports one fully scoped Direct model response,
with text/status/outcome events and instance-local stores. The development page
calls real Bedrock through the package's optional provider adapter.

Each submission currently creates an independent conversation. Continuation,
durable recovery, discovery, tools, queue, and steer are subsequent review steps;
unsupported operations raise explicitly. `get_run()` and `serve_mcp()` remain
unimplemented. Workers follows in PR3.

| Part                    | Responsibility                                                           |
| ----------------------- | ------------------------------------------------------------------------ |
| `main.py`               | Public `LPAgent` facade and immutable execution configuration            |
| `types.py`              | Serializable requests, events, outcomes, questions, and adapter data     |
| `interfaces.py`         | Async run-handle and host-service contracts                              |
| `identity.py`           | Live services and verified context, separate from serialized data        |
| `errors.py`             | Validation, access, and busy errors before acceptance                    |
| `utils/audit.py`        | Canonical instruction snapshots and their versioned SHA-256 fingerprints |
| `flows/`                | Scope preparation, model steps, prompts, state transitions, and outcomes |
| `runtimes/`             | Admission, owned Direct tasks, shutdown, and synchronous event streaming |
| `adapters/`             | Bedrock, environment assembly, and temporary memory stores               |
| `corpus/`               | Corpus retrieval functions called by task flows                          |
| `litigant_portal.agent` | Thin identity translation and options forwarding for the Django caller   |

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


def configured_agent(identity_id, load_model, load_api_key, resource_root):
    return LPAgent(
        environment=create_environment(
            identity_id=identity_id,
            court="north-dakota",
            topic="adult-name-change",
            model=load_model,
            api_key=load_api_key,
            resource_root=resource_root,
        )
    )
```

`court` and `topic` are optional strings. The caller's UI or deployment defaults
choose these keys; the agent owns their resource lookup. Neither argument accepts
a callback, and there is no caller-supplied catalogue.

Identity, model, judge, API key, and resource root accept values or synchronous
zero-argument callbacks. Callbacks run once during initialization and may perform I/O. Their
resolved values are validated; callbacks are not retained or invoked during a
run. Async callbacks are rejected. The factory does not read Django settings,
query application models, or discover credentials from environment variables.

`judge` configures a future evaluation model. An explicit judge uses its own
allowlisted Bedrock model with the same credentials. When omitted or resolved to
`None`, `ResourceScope` uses the primary model client without resolving the
model callback again. No evaluation calls run yet.

Pass `resource_root` as the directory containing `corpus/`; the factory captures
an absolute `Path` for later retrieval. Initialization and scope binding perform
no corpus lookup. The directory and selected scope must exist when file retrieval
is called, not when an agent is constructed.

The adapter exports `lp_agent.adapters.bedrock.MODEL_CHOICES` for selectors and
requires an explicit API key. The key stays in live adapter configuration, outside
serializable run configuration, checkpoints, and events. LiteLLM loads only when
the Bedrock adapter executes a request.

`PortalAgent(identity=..., model=..., judge=None, court=None, topic=None, ...)` requires a
saved registered or anonymous `UserIdentity`, including a middleware lazy wrapper,
before invoking any initialization callbacks. It converts that identity's primary
key to an opaque string and forwards these options to the factory. The wrapper
supplies `settings.BASE_DIR` as the resource root and wraps
`settings.BEDROCK_API_KEY` in `SecretStr`. That setting reads the existing
`AWS_BEARER_TOKEN_BEDROCK` environment variable. Identity stays an explicit
constructor argument; the view passes `request.identity`. It inherits agent
methods and defaults to `Workers`, which is still unimplemented.
The development view selects `Direct`, supplies the
selected court/topic keys, and uses the Site assistant model as
the page's default when supported. Otherwise the page requires an explicit model
selection. Authentication and HTTP input validation remain in Django.

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

`AgentValidationError`, `AgentAccessError`, and `AgentBusyError` reject invalid or
unauthorized submissions and replies before acceptance. After acceptance,
execution failures produce a `FailedOutcome` containing a caller-safe `PublicError`.
Constructing data models directly uses Pydantic's `ValidationError`.
Wrapped validation errors expose only known contract field paths and controlled
messages. Unknown keys, dictionary keys, and submitted values are not echoed.

## Scope and services

The host verifies both signed-in and anonymous identity and supplies an
`AccessContext(identity_id=...)`. This value asserts host verification; it does
not authenticate a caller. Service adapters enforce permissions on every operation.

`AgentIdentity` contains that context, conversation/run stores, a scope factory,
and `ScopeSelection(court=None, topic=None)`. The selection can
also supply either or both identifiers. Constructing this dataclass or `LPAgent`
does not invoke services. The optional environment factory does invoke any
supplied initialization callbacks, as described above.

Normal execution requires both court and topic. The factory binds a
`ResourceScope` with the same identity, a full `Scope`, primary and judge
model clients, and a resource root. The instance binds once. An omitted judge
defaults to the primary model, and the resource root may be absent when file
retrieval is unused. Corpus retrieval is provided by the functions below.
Court/topic choices and their `Court` representation belong to the development
page's selector, outside the package.

### Corpus retrieval

The async functions in `lp_agent/corpus/` accept court/topic keys and are intended
for calls from `lp_agent/flows/`:

| Function                                                | Result                       | Current behavior             |
| ------------------------------------------------------- | ---------------------------- | ---------------------------- |
| `get_database_corpus(court, topic)`                     | `tuple[CorpusDocument, ...]` | Raises `NotImplementedError` |
| `get_s3_corpus(court, topic)`                           | `tuple[CorpusDocument, ...]` | Raises `NotImplementedError` |
| `get_vector_corpus(court, topic, *, query)`             | `tuple[SearchHit, ...]`      | Raises `NotImplementedError` |
| `get_file_based_corpus(court, topic, *, resource_root)` | `tuple[CorpusDocument, ...]` | Reads existing YAML files    |

`CorpusDocument` contains raw `content` and a `SourceReference`. The temporary file
reader loads `corpus/courts/<court>/court.yml` and every `.yml`/`.yaml` file in
`corpus/courts/<court>/topics/<topic>/`, requiring `topic.yml` to exist. It reads
UTF-8 off the event loop, returns documents in path order, and uses paths relative
to the resource root as source IDs and locators. Missing or unreadable corpus and
paths escaping the selected scope raise `AgentValidationError`. It needs neither
PyYAML nor Django and does not resolve legacy prompt directories.

Flows are generic orchestration or task logic, possibly for a task such as name
change. Court-specific YAML files are corpus data, not Python flow modules.
Retrieval is not yet wired into model context; the current prompt still states
that court documents are unavailable.

Vector search will return ranked `SearchHit` values with relevance and provenance.
Relevance filtering and returned-context limits belong in procedural tool code.
Private-document retrieval and its authorization remain future work.

Prompts, tools, and discovery belong to flows; runtimes decide how flows execute.
Provider clients, storage connections, and optional Django model access belong to
package adapters with caller-supplied configuration. Only contract models are
serialized with `model_dump_json()` and restored
with `model_validate_json()`; use Pydantic `TypeAdapter` for unions such as
`RunOutcome`. Service environments are never checkpoint or event payloads.

## Model data and instruction audits

The model boundary uses our own Pydantic types matching a supported subset of the
[OpenAI Responses format](https://developers.openai.com/api/docs/guides/function-calling).
It does not import the OpenAI SDK or implement the complete Responses HTTP API.
The Bedrock adapter uses LiteLLM’s asynchronous Responses interface. GPT models
use native Responses; GLM uses LiteLLM’s chat translation. Model choices and
credentials remain supplied by the host. Provider storage and response
caching are disabled; native Responses requests include encrypted reasoning
continuation data. Reasoning effort uses provider defaults.

Translated requests reject reasoning continuation and message metadata that
LiteLLM cannot preserve. Native Responses input retains those fields.

- `ModelRequest` contains resolved `instructions`, ordered `input` items, and
  function `tools`. Model selection, credentials, and transport configuration
  belong to the adapter. Put resolved system instructions in `instructions` so
  there is one source for the instruction artifact.
- `ModelMessage` uses `type="message"`, `role`, and `content`. The current subset
  supports text inputs, assistant text/refusals, and assistant metadata including
  IDs, status, annotations, log probabilities, and `phase`. Multimodal inputs and
  provider-hosted tools are outside this contract. Unsupported fields/items fail
  validation rather than being silently dropped.
- `ToolCall` uses `type="function_call"`, `call_id`, `name`, and an unmodified JSON
  argument **string**. `FunctionCallOutput` uses `type="function_call_output"`,
  the same `call_id`, and an output string. PR2 parses and validates arguments
  against the allowlisted tool before dispatch; preserving a string is not
  permission to execute it.
- `ReasoningItem` retains summary/content, encrypted continuation data, ID, and
  status. `Conversation.items` defines ordered history for the persistence step;
  the current flow retains input and output in its run checkpoint.
  [Reasoning continuation items](https://developers.openai.com/api/docs/guides/reasoning)
  and assistant metadata must survive persistence and subsequent model calls.
- `ModelClient.stream()` yields `ModelTextDelta`, `ModelOutputItem`, and
  `ModelFinished` events. Streams support `aclose()`.
  Adapters assemble complete output items in provider order, including reasoning
  and function calls. Deltas serve live display; assembled items become history
  once, without duplicating the text. Item status remains authoritative: an
  assembled item can be incomplete. A successful response needs completed
  assistant output and a successful terminal signal; EOF alone is insufficient.
  Reasoning data is not public text. Completed items received before a stream
  failure remain in the failed run's checkpoint. Each model call owns its HTTP
  client; the adapter closes both the response stream and client before returning,
  including on failure, timeout, or cancellation.

Function tools serialize as `type`, `name`, `description`, `parameters`, and
`strict`. Strict mode defaults to `true` and is always serialized. Parameters
must describe an object. Strict schemas close every object with
`additionalProperties: false` and list every property in `required`; represent
optional values using a nullable type. The validators beside `ToolDefinition` in `types.py` check these structural rules
through nested objects, arrays, alternatives, and local references. Example and
default data are preserved, including nulls. An explicit `strict=False` permits
open objects and optional properties. Adapters must check any additional schema
restrictions of their target model and reject unsupported strict mode rather
than silently disabling it.

Absent optional API metadata is omitted during serialization. Tool defaults are
explicit; existing unreleased `messages`, `text`, and `input_schema` model shapes
have no compatibility aliases. Application run controls, scope, identity,
confirmations, and browser events retain their own contracts. MCP will translate
shared tool definitions into its own protocol through the same runner.

`lp_agent.utils.audit.InstructionArtifact.from_request(request)` snapshots instructions and tool
definitions without retaining references to the request's mutable schemas.
`canonical_bytes()` produces UTF-8 JSON containing `format`, `instructions`, and
`tools`; `content_hash()` returns its SHA-256 digest. Version
`lp_agent.instructions.v1` fixes sorted object keys, compact separators, explicit
defaults, finite numbers, exact string content, and preserved array order.
Dictionary insertion order does not affect the fingerprint; tool order does.
Changes to this serialization contract require a new format version and fixture.

Current in-memory checkpoints retain the model request, ordered assembled output,
terminal signal, and an instruction artifact containing `canonical_json` and
`sha256`. The canonical JSON string round-trips to the artifact’s exact UTF-8
bytes. Reasoning and output metadata stay in that internal checkpoint, outside
browser events and ordinary logs. Durable restricted audit storage follows in
the persistence step; these instance-local records do not survive restart.
The fingerprint identifies canonical instructions and tools, not conversation
input, model configuration, or every byte of an adapted provider request.
The current chat engine's artifacts are unchanged, and old hash compatibility
is not required before release. This step adds no audit database or migration.

## Remaining PR2 contract

The full PR2 interface extends the current independent-response path with
continuation, discovery, and recovery:

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

Missing scope will use fixed procedural questions without a model call.
Discovery execution and its choice source remain unimplemented. With only a
court, ask for its topic; with
only a topic, ask for a compatible court; with neither, ask court then topic.
Use `ChoiceQuestion`, `ChoiceAnswer`, and `respond()` for these replies. Discovery
preserves the original message and run ID, releases execution resources between
replies, binds scope once, and automatically continues the original message.
Missing scope remains valid at construction; executing discovery is PR2 step 4,
after persistence in step 3. The current development page still requires both keys.
The page exposes model, scope, message, and active-time controls. Disabled controls
for future interruption policies and step limits are omitted.
Durable conversation and checkpoint storage will support authorized recovery after
replacing the agent or restarting the process.

### Execution policy

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

From the repository root, run `tox -e agent`. Default `tox` and `make test` also run
this environment. It installs only Pydantic (at least 2.10.0) and pytest,
disables plugin autoload, and requires neither Django nor a
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
stream cleanup. Provider tests exercise LiteLLM's actual native and translated
stream wrappers with controlled HTTP responses or completion streams, including
reasoning metadata, terminal status, failure checkpoints, and cancellation.
Local HTTP fixtures also check that repeated synchronous requests close client
connections before their event loops are discarded. They make no live model calls.
