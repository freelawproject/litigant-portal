"""
Provider- and transport-independent data exchanged with the agent.
"""

from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StrictInt,
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
    max_active_seconds: Annotated[float, Field(gt=0, strict=True)] = 300
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


class ToolCall(ContractModel):
    """
    A normalized model-selected call with fully assembled arguments.
    """

    call_id: Identifier
    name: Identifier
    arguments: dict[str, JsonValue]


class ModelMessage(ContractModel):
    """
    Model context independent of provider response classes.
    """

    role: Literal["system", "user", "assistant", "tool"]
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: Identifier | None = None

    @model_validator(mode="after")
    def valid_tool_message(self) -> Self:
        """
        Associate tool results with calls made by assistant messages.
        """
        if (self.role == "tool") != (self.tool_call_id is not None):
            raise ValueError("tool_call_id is required only for tool messages")
        if self.tool_calls and self.role != "assistant":
            raise ValueError("only assistant messages may contain tool calls")
        return self


class ToolDefinition(ContractModel):
    name: Identifier
    description: NonBlankText
    input_schema: dict[str, JsonValue]


class ModelRequest(ContractModel):
    """
    One model operation; provider configuration belongs to its adapter.
    """

    messages: tuple[ModelMessage, ...]
    tools: tuple[ToolDefinition, ...] = ()


class ModelTextDelta(ContractModel):
    type: Literal["text"] = "text"
    delta: str


class ModelToolCall(ContractModel):
    type: Literal["tool_call"] = "tool_call"
    call: ToolCall


class ModelFinished(ContractModel):
    """
    Distinguish a finished response from a truncated or broken stream.
    """

    type: Literal["finished"] = "finished"
    reason: Literal["stop", "length", "tool_calls", "content_filter", "other"]


type ModelEvent = Annotated[
    ModelTextDelta | ModelToolCall | ModelFinished, Field(discriminator="type")
]


class Conversation(ContractModel):
    """
    An authorized conversation snapshot, separate from an agent instance.
    """

    conversation_id: Identifier
    identity_id: Identifier
    scope: ScopeSelection
    messages: tuple[ModelMessage, ...] = ()
