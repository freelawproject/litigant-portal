"""
Agent contracts and Responses-compatible model data, without SDK dependencies.
"""

import json
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictBool,
    StrictInt,
    model_serializer,
    model_validator,
)


def _not_blank(value: str) -> str:
    """
    Reject whitespace-only values without altering valid content.
    """
    if not value.strip():
        raise ValueError("must not be blank")
    return value


type Identifier = Annotated[str, AfterValidator(_not_blank)]
type NonBlankText = Annotated[str, AfterValidator(_not_blank)]
type Runtime = Literal["Direct", "Workers"]
type InterruptBehavior = Literal["reject", "queue", "steer"]
type RunState = Literal[
    "queued",
    "running",
    "waiting_for_input",
    "completed",
    "failed",
    "cancelled",
]


class ContractModel(BaseModel):
    """
    Validate known fields and finite numbers; prevent field reassignment.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class RunLimits(ContractModel):
    """
    Cumulative budgets, excluding queue time and time waiting for input.
    """

    max_steps: Annotated[StrictInt, Field(gt=0)] = 30
    max_active_seconds: Annotated[float, Field(gt=0, strict=True)] = 300.0
    max_restarts: Annotated[StrictInt, Field(ge=0)] = 2


class AgentConfiguration(ContractModel):
    """
    Execution choices fixed for an instance and persisted with a run.
    """

    runtime: Runtime = "Direct"
    interrupt_behavior: InterruptBehavior = "reject"
    limits: RunLimits = Field(default_factory=RunLimits)


class AccessContext(ContractModel):
    """
    An opaque identity verified by the host, including anonymous users.
    """

    identity_id: Identifier


class ScopeSelection(ContractModel):
    """
    Host-supplied scope, which may still require procedural discovery.
    """

    court: Identifier | None = None
    topic: Identifier | None = None


class Scope(ContractModel):
    """
    Complete court and topic scope required for normal execution.
    """

    court: Identifier
    topic: Identifier


class RunRequest(ContractModel):
    """
    A message and references to its conversation and authorized attachments.
    """

    message: NonBlankText
    conversation_id: Identifier | None = None
    attachment_ids: tuple[Identifier, ...] = ()


class Choice(ContractModel):
    """
    One host-validated option presented to the user.
    """

    choice_id: Identifier
    label: NonBlankText


class ChoiceAnswer(ContractModel):
    """
    A selection checked against the pending question by the runtime.
    """

    choice_id: Identifier


class ChoiceQuestion(ContractModel):
    """
    A choice question that survives run suspension and reconstruction.
    """

    question_id: Identifier
    prompt: NonBlankText
    choices: Annotated[tuple[Choice, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def unique_choices(self) -> Self:
        """
        Keep replies unambiguous within a question.
        """
        ids = [choice.choice_id for choice in self.choices]
        if len(ids) != len(set(ids)):
            raise ValueError("choice IDs must be unique")
        return self


class QuestionReply(ContractModel):
    """
    An answer addressed to a particular pending question.
    """

    question_id: Identifier
    answer: ChoiceAnswer


class RunReference(ContractModel):
    """
    Stable identifiers shared by status, events, and terminal outcomes.
    """

    run_id: Identifier
    conversation_id: Identifier


class RunStatus(RunReference):
    """
    A recoverable status snapshot, including the question while paused.
    """

    state: RunState
    pending_question: ChoiceQuestion | None = None

    @model_validator(mode="after")
    def question_matches_state(self) -> Self:
        """
        Require a question exactly when the run is waiting for input.
        """
        if (self.state == "waiting_for_input") != (
            self.pending_question is not None
        ):
            raise ValueError(
                "pending_question is required only for waiting_for_input"
            )
        return self


class PublicError(ContractModel):
    """
    A stable code and caller-safe explanation, without exception data.
    """

    code: Identifier
    message: NonBlankText


class SourceReference(ContractModel):
    """
    Provenance for a court source or an authorized private document.
    """

    source_id: Identifier
    kind: Literal["corpus", "document"]
    title: NonBlankText
    locator: str | None = None


class CorpusDocument(ContractModel):
    """
    Corpus content and provenance, without an artificial relevance score.
    """

    content: str
    source: SourceReference


class SearchHit(ContractModel):
    """
    Ranked content; scores use the search adapter's documented scale.
    """

    content: str
    score: float
    source: SourceReference


class CompletedOutcome(RunReference):
    state: Literal["completed"] = "completed"
    text: str
    sources: tuple[SourceReference, ...] = ()


class FailedOutcome(RunReference):
    state: Literal["failed"] = "failed"
    error: PublicError


class CancelledOutcome(RunReference):
    state: Literal["cancelled"] = "cancelled"


type RunOutcome = Annotated[
    CompletedOutcome | FailedOutcome | CancelledOutcome,
    Field(discriminator="state"),
]


class TextEvent(ContractModel):
    type: Literal["text"] = "text"
    delta: str


class ToolEvent(ContractModel):
    type: Literal["tool"] = "tool"
    call_id: Identifier
    name: Identifier
    state: Literal["started", "completed", "failed", "skipped"]
    data: JsonValue = None


class QuestionEvent(ContractModel):
    type: Literal["question"] = "question"
    question: ChoiceQuestion


class StatusEvent(ContractModel):
    type: Literal["status"] = "status"
    status: RunStatus


class OutcomeEvent(ContractModel):
    type: Literal["outcome"] = "outcome"
    outcome: RunOutcome


type EventPayload = Annotated[
    TextEvent | ToolEvent | QuestionEvent | StatusEvent | OutcomeEvent,
    Field(discriminator="type"),
]


class RunEvent(RunReference):
    """
    A serializable event; attempt distinguishes output across restarts.
    """

    attempt: Annotated[StrictInt, Field(ge=1)] = 1
    payload: EventPayload

    @model_validator(mode="after")
    def matching_reference(self) -> Self:
        """
        Keep envelope and nested status/outcome identifiers consistent.
        """
        reference: RunReference | None = None
        if isinstance(self.payload, StatusEvent):
            reference = self.payload.status
        elif isinstance(self.payload, OutcomeEvent):
            reference = self.payload.outcome
        if reference is not None and (
            reference.run_id != self.run_id
            or reference.conversation_id != self.conversation_id
        ):
            raise ValueError("event and payload run references must match")
        return self


class RunCheckpoint(RunReference):
    """
    Versioned executor state; PR2 defines its payload and atomic commits.
    """

    version: Literal[1] = 1
    data: dict[str, JsonValue]


class ResponsesModel(ContractModel):
    """
    Omit absent metadata while retaining nulls inside JSON content and schemas.
    """

    @model_serializer(mode="wrap")
    def serialize_present_fields(self, serialize):
        """
        Optional API fields are absent unless they have a value.
        """
        return {
            key: value
            for key, value in serialize(self).items()
            if value is not None
        }


class InputText(ResponsesModel):
    type: Literal["input_text"] = "input_text"
    text: str


class OutputText(ResponsesModel):
    type: Literal["output_text"] = "output_text"
    text: str
    annotations: tuple[dict[str, JsonValue], ...] = ()
    logprobs: tuple[dict[str, JsonValue], ...] | None = None


class Refusal(ResponsesModel):
    type: Literal["refusal"] = "refusal"
    refusal: str


type MessageContent = Annotated[
    InputText | OutputText | Refusal, Field(discriminator="type")
]
type ModelItemStatus = Literal["in_progress", "completed", "incomplete"]


class ModelMessage(ResponsesModel):
    """
    Text input or assistant output in the Responses message representation.
    """

    type: Literal["message"] = "message"
    role: Literal["system", "developer", "user", "assistant"]
    content: str | tuple[MessageContent, ...]
    id: Identifier | None = None
    status: ModelItemStatus | None = None
    phase: Literal["commentary", "final_answer"] | None = None

    @model_validator(mode="after")
    def valid_message_role(self) -> Self:
        """
        Keep assistant-only metadata and output content on assistant messages.
        """
        if self.role != "assistant":
            if self.id is not None or self.phase is not None:
                raise ValueError(
                    "only assistant messages carry output metadata"
                )
            if not isinstance(self.content, str) and any(
                not isinstance(part, InputText) for part in self.content
            ):
                raise ValueError("input messages require input text")
        return self


class ToolCall(ResponsesModel):
    """
    An assembled function call; PR2 parses and validates arguments for dispatch.
    """

    type: Literal["function_call"] = "function_call"
    call_id: Identifier
    name: Identifier
    arguments: str
    id: Identifier | None = None
    status: ModelItemStatus | None = None


class FunctionCallOutput(ResponsesModel):
    type: Literal["function_call_output"] = "function_call_output"
    call_id: Identifier
    output: str
    id: Identifier | None = None
    status: ModelItemStatus | None = None


class ReasoningSummary(ResponsesModel):
    type: Literal["summary_text"] = "summary_text"
    text: str


class ReasoningText(ResponsesModel):
    type: Literal["reasoning_text"] = "reasoning_text"
    text: str


class ReasoningItem(ResponsesModel):
    """
    Continuation data retained in model history, not emitted as public text.
    """

    type: Literal["reasoning"] = "reasoning"
    id: Identifier
    summary: tuple[ReasoningSummary, ...]
    content: tuple[ReasoningText, ...] | None = None
    encrypted_content: str | None = None
    status: ModelItemStatus | None = None


type ModelItem = Annotated[
    ModelMessage | ToolCall | FunctionCallOutput | ReasoningItem,
    Field(discriminator="type"),
]


def _resolve_schema_reference(parameters: dict, reference: str) -> dict:
    """
    Resolve a local JSON pointer without fetching external schema resources.
    """
    if not isinstance(reference, str) or not (
        reference == "#" or reference.startswith("#/")
    ):
        raise ValueError("parameter schemas require local references")
    target = parameters
    tokens = reference[2:].split("/") if reference != "#" else ()
    for token in tokens:
        token = token.replace("~1", "/").replace("~0", "~")
        if not isinstance(target, dict) or token not in target:
            raise ValueError("schema reference does not resolve")
        target = target[token]
    if not isinstance(target, dict):
        raise ValueError("schema references must resolve to objects")
    return target


def _validate_tool_parameters(parameters: dict, *, strict: bool) -> None:
    """
    Require finite JSON and closed, fully required objects in strict schemas.

    Walk schema keywords, not example/default data. Provider adapters must
    additionally check the schema features supported by their target model.
    """
    json.dumps(parameters, allow_nan=False)
    root = parameters
    root_references = set()
    while "$ref" in root:
        if id(root) in root_references:
            raise ValueError("root reference must resolve to an object schema")
        root_references.add(id(root))
        root = _resolve_schema_reference(parameters, root["$ref"])
    if root.get("type") != "object":
        raise ValueError("function parameters must describe an object")
    if not strict:
        return

    pending = [parameters]
    visited = set()
    while pending:
        schema = pending.pop()
        if not isinstance(schema, dict):
            raise ValueError("schema nodes must be objects")
        if id(schema) in visited:
            continue
        visited.add(id(schema))

        if "$ref" in schema:
            pending.append(
                _resolve_schema_reference(parameters, schema["$ref"])
            )

        kind = schema.get("type")
        is_object = kind == "object" or (
            isinstance(kind, list) and "object" in kind
        )
        if is_object or "properties" in schema:
            properties = schema.get("properties", {})
            required = schema.get("required", [])
            if (
                not is_object
                or not isinstance(properties, dict)
                or not isinstance(required, list)
                or not all(isinstance(name, str) for name in required)
                or len(required) != len(properties)
                or set(required) != set(properties)
                or schema.get("additionalProperties") is not False
                or "patternProperties" in schema
            ):
                raise ValueError(
                    "strict objects must forbid extra properties and require every property"
                )

        for keyword in ("properties", "$defs"):
            children = schema.get(keyword, {})
            if not isinstance(children, dict):
                raise ValueError("schema property definitions must be objects")
            pending.extend(children.values())
        if "items" in schema:
            pending.append(schema["items"])
        for keyword in ("anyOf", "oneOf", "allOf", "prefixItems"):
            children = schema.get(keyword, [])
            if not isinstance(children, list):
                raise ValueError("schema alternatives must be arrays")
            pending.extend(children)


class ToolDefinition(ResponsesModel):
    """
    Responses function schema; adapters must not silently disable strict mode.
    """

    type: Literal["function"] = "function"
    name: Identifier
    description: NonBlankText
    parameters: dict[str, JsonValue]
    strict: StrictBool = True

    @model_validator(mode="after")
    def valid_parameters(self) -> Self:
        """
        Check the common strict-schema requirements before adapter invocation.
        """
        _validate_tool_parameters(self.parameters, strict=self.strict)
        return self


class ModelRequest(ResponsesModel):
    """
    Responses input; model selection, credentials, and transport stay in adapters.
    """

    instructions: str = ""
    input: tuple[ModelItem, ...]
    tools: tuple[ToolDefinition, ...] = ()

    @model_validator(mode="after")
    def unique_tools(self) -> Self:
        """
        Require unambiguous names for dispatch.
        """
        names = [tool.name for tool in self.tools]
        if len(names) != len(set(names)):
            raise ValueError("tool names must be unique")
        return self


class ModelTextDelta(ContractModel):
    type: Literal["text"] = "text"
    delta: str


class ModelOutputItem(ContractModel):
    """
    An assembled output item in provider order, alongside incremental text.
    """

    type: Literal["output_item"] = "output_item"
    item: Annotated[
        ModelMessage | ToolCall | ReasoningItem, Field(discriminator="type")
    ]

    @model_validator(mode="after")
    def assistant_output_only(self) -> Self:
        """
        The model emits assistant output, not input content or tool results.
        """
        if isinstance(self.item, ModelMessage):
            if self.item.role != "assistant":
                raise ValueError(
                    "model output messages must have the assistant role"
                )
            if not isinstance(self.item.content, str) and any(
                isinstance(part, InputText) for part in self.item.content
            ):
                raise ValueError("model output cannot contain input text")
        return self


class ModelFinished(ContractModel):
    """
    Distinguish a finished response from a truncated or broken stream.
    """

    type: Literal["finished"] = "finished"
    reason: Literal["stop", "length", "tool_calls", "content_filter", "other"]


type ModelEvent = Annotated[
    ModelTextDelta | ModelOutputItem | ModelFinished,
    Field(discriminator="type"),
]


class Conversation(ContractModel):
    """
    An authorized conversation snapshot, separate from an agent instance.
    """

    conversation_id: Identifier
    identity_id: Identifier
    scope: ScopeSelection
    items: tuple[ModelItem, ...] = ()
