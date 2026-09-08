import json

import pytest
from pydantic import TypeAdapter, ValidationError

from lp_agent.types import (
    CancelledOutcome,
    Choice,
    ChoiceAnswer,
    ChoiceQuestion,
    CompletedOutcome,
    FailedOutcome,
    ModelMessage,
    ModelRequest,
    OutcomeEvent,
    PublicError,
    QuestionEvent,
    QuestionReply,
    RunCheckpoint,
    RunEvent,
    RunLimits,
    RunOutcome,
    RunRequest,
    RunStatus,
    Scope,
    ScopeSelection,
    SearchHit,
    SourceReference,
    StatusEvent,
    TextEvent,
    ToolCall,
    ToolEvent,
)

REFERENCE = {"run_id": "run-1", "conversation_id": "conversation-1"}
QUESTION = ChoiceQuestion(
    question_id="court-question",
    prompt="Which court?",
    choices=(Choice(choice_id="court-1", label="Example court"),),
)


def test_request_round_trip_preserves_message_and_attachment_order():
    request = RunRequest(
        message="  A question\n",
        conversation_id="conversation-1",
        attachment_ids=("document-2", "document-1"),
    )
    encoded = request.model_dump_json()
    assert json.loads(encoded)["message"] == "  A question\n"
    assert RunRequest.model_validate_json(encoded) == request


@pytest.mark.parametrize(
    "limits",
    [
        {"max_steps": 0},
        {"max_steps": True},
        {"max_steps": 1.5},
        {"max_active_seconds": 0},
        {"max_active_seconds": float("inf")},
        {"max_active_seconds": float("nan")},
        {"max_active_seconds": True},
        {"max_restarts": -1},
        {"max_restarts": False},
    ],
)
def test_invalid_budgets_are_rejected(limits):
    with pytest.raises(ValidationError):
        RunLimits(**limits)


def test_disabling_restarts_and_fractional_time_are_supported():
    assert RunLimits(max_restarts=0, max_active_seconds=0.5).max_restarts == 0


def test_partial_scope_is_distinct_from_execution_scope():
    assert ScopeSelection(topic="topic-1").court is None
    with pytest.raises(ValidationError):
        Scope(topic="topic-1")
    with pytest.raises(ValidationError):
        Scope(court="court-1", topic=" ")


def test_question_and_reply_survive_serialization():
    reply = QuestionReply(
        question_id=QUESTION.question_id,
        answer=ChoiceAnswer(choice_id="court-1"),
    )
    assert (
        ChoiceQuestion.model_validate_json(QUESTION.model_dump_json())
        == QUESTION
    )
    assert QuestionReply.model_validate_json(reply.model_dump_json()) == reply


@pytest.mark.parametrize("choices", [(), QUESTION.choices * 2])
def test_choice_questions_require_unambiguous_options(choices):
    with pytest.raises(ValidationError):
        ChoiceQuestion(
            question_id="question", prompt="Choose", choices=choices
        )


def test_only_waiting_status_carries_a_pending_question():
    paused = RunStatus(
        **REFERENCE, state="waiting_for_input", pending_question=QUESTION
    )
    assert RunStatus.model_validate_json(paused.model_dump_json()) == paused
    with pytest.raises(ValidationError):
        RunStatus(**REFERENCE, state="waiting_for_input")
    with pytest.raises(ValidationError):
        RunStatus(**REFERENCE, state="completed", pending_question=QUESTION)
    with pytest.raises(ValidationError):
        TypeAdapter(RunOutcome).validate_python(paused.model_dump())


@pytest.mark.parametrize(
    "outcome",
    [
        CompletedOutcome(**REFERENCE, text="Answer"),
        FailedOutcome(
            **REFERENCE,
            error=PublicError(
                code="model_failed", message="Please try again."
            ),
        ),
        CancelledOutcome(**REFERENCE),
    ],
)
def test_outcome_union_preserves_terminal_type(outcome):
    adapter = TypeAdapter(RunOutcome)
    assert adapter.validate_json(adapter.dump_json(outcome)) == outcome
    assert adapter.json_schema()["discriminator"]["propertyName"] == "state"


@pytest.mark.parametrize(
    "payload",
    [
        TextEvent(delta="Incremental text"),
        ToolEvent(call_id="call-1", name="search", state="skipped"),
        QuestionEvent(question=QUESTION),
        StatusEvent(status=RunStatus(**REFERENCE, state="running")),
        OutcomeEvent(outcome=CompletedOutcome(**REFERENCE, text="Answer")),
    ],
)
def test_event_round_trip_restores_typed_payload(payload):
    event = RunEvent(**REFERENCE, attempt=2, payload=payload)
    restored = RunEvent.model_validate_json(event.model_dump_json())
    assert restored == event
    assert type(restored.payload) is type(payload)


def test_event_rejects_mismatched_run_and_unknown_payload():
    with pytest.raises(ValidationError):
        RunEvent(
            **REFERENCE,
            payload=StatusEvent(
                status=RunStatus(
                    run_id="different-run",
                    conversation_id=REFERENCE["conversation_id"],
                    state="running",
                )
            ),
        )
    with pytest.raises(ValidationError):
        RunEvent(**REFERENCE, payload={"type": "raw_provider_response"})


def test_checkpoint_envelope_round_trip():
    checkpoint = RunCheckpoint(
        **REFERENCE, data={"original_message": "Hello", "steps": 0}
    )
    assert (
        RunCheckpoint.model_validate_json(checkpoint.model_dump_json())
        == checkpoint
    )
    with pytest.raises(ValidationError):
        RunCheckpoint(**REFERENCE, version=2, data={})


@pytest.mark.parametrize("value", [object(), float("inf"), float("nan")])
def test_json_payloads_reject_live_objects_and_nonfinite_numbers(value):
    with pytest.raises(ValidationError):
        RunCheckpoint(**REFERENCE, data={"nested": [value]})
    with pytest.raises(ValidationError):
        ToolEvent(call_id="call", name="search", state="completed", data=value)


def test_contract_rejects_undeclared_provider_fields():
    with pytest.raises(ValidationError):
        RunRequest(message="Hello", provider_response={"id": "raw"})


def test_model_context_and_search_provenance_are_portable():
    call = ToolCall(
        call_id="call-1", name="search", arguments={"query": "help"}
    )
    request = ModelRequest(
        messages=(
            ModelMessage(role="user", text="Help"),
            ModelMessage(role="assistant", tool_calls=(call,)),
            ModelMessage(
                role="tool", text="Relevant text", tool_call_id="call-1"
            ),
        )
    )
    assert (
        ModelRequest.model_validate_json(request.model_dump_json()) == request
    )
    hit = SearchHit(
        content="Relevant text",
        score=2.5,
        source=SourceReference(
            source_id="source-1", kind="corpus", title="Example court guide"
        ),
    )
    assert SearchHit.model_validate_json(hit.model_dump_json()) == hit
    with pytest.raises(ValidationError):
        ModelMessage(role="tool", text="Unmatched output")
