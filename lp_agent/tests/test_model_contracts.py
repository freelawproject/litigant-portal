import json
from copy import deepcopy
from typing import Self

import pytest
from pydantic import TypeAdapter, ValidationError

from lp_agent.types import (
    ContractModel,
    Conversation,
    FunctionCallOutput,
    ModelEvent,
    ModelMessage,
    ModelOutputItem,
    ModelRequest,
    ScopeSelection,
    ToolCall,
    ToolDefinition,
)

PARAMETERS = {
    "type": "object",
    "properties": {"query": {"type": "string"}},
    "required": ["query"],
    "additionalProperties": False,
}

HISTORY = [
    {"type": "message", "role": "user", "content": "Help\n"},
    {
        "type": "reasoning",
        "id": "reasoning-1",
        "summary": [{"type": "summary_text", "text": "Look up guidance"}],
        "content": [
            {"type": "reasoning_text", "text": "Provider continuation"}
        ],
        "encrypted_content": "opaque-continuation",
        "status": "completed",
    },
    {
        "type": "function_call",
        "id": "item-1",
        "call_id": "call-1",
        "name": "lookup",
        "arguments": '{ "query": "help" }',
        "status": "completed",
    },
    {
        "type": "function_call_output",
        "call_id": "call-1",
        "output": "Guidance",
    },
    {
        "type": "message",
        "id": "message-1",
        "role": "assistant",
        "phase": "final_answer",
        "status": "completed",
        "content": [
            {
                "type": "output_text",
                "text": "Here is guidance.",
                "annotations": [
                    {
                        "type": "url_citation",
                        "url": "https://example.invalid",
                        "title": "Guide",
                        "start_index": 0,
                        "end_index": 8,
                    }
                ],
                "logprobs": [],
            }
        ],
    },
]


def test_responses_request_and_conversation_preserve_complete_items():
    payload = {
        "instructions": " Help the user.\n",
        "input": HISTORY,
        "tools": [],
    }
    request = ModelRequest.model_validate(payload)
    assert json.loads(request.model_dump_json()) == payload
    assert (
        ModelRequest.model_validate_json(request.model_dump_json()) == request
    )
    conversation = Conversation(
        conversation_id="conversation",
        identity_id="identity",
        scope=ScopeSelection(),
        items=request.input,
    )
    restored = Conversation.model_validate_json(conversation.model_dump_json())
    assert json.loads(restored.model_dump_json())["items"] == HISTORY


@pytest.mark.parametrize("item", [HISTORY[1], HISTORY[2], HISTORY[4]])
def test_output_events_preserve_items_for_the_next_request(item):
    event = ModelOutputItem(item=item)
    adapter = TypeAdapter(ModelEvent)
    restored = adapter.validate_json(adapter.dump_json(event))
    assert json.loads(restored.model_dump_json())["item"] == item


def test_text_deltas_remain_separate_from_history_items():
    event = TypeAdapter(ModelEvent).validate_python(
        {"type": "text", "delta": "Hi"}
    )
    assert event.delta == "Hi"
    for item in [
        HISTORY[0],
        HISTORY[3],
        {
            "type": "message",
            "role": "assistant",
            "content": [{"type": "input_text", "text": "Wrong content type"}],
        },
    ]:
        with pytest.raises(ValidationError):
            ModelOutputItem(item=item)


def test_refusals_and_incomplete_status_are_preserved():
    message = ModelMessage.model_validate(
        {
            "role": "assistant",
            "status": "incomplete",
            "content": [
                {"type": "refusal", "refusal": "Cannot help with that"}
            ],
        }
    )
    assert (
        ModelMessage.model_validate_json(message.model_dump_json()) == message
    )
    assert message.content[0].refusal == "Cannot help with that"
    with pytest.raises(ValidationError):
        ModelMessage(role="user", content="Hi", phase="final_answer")


def test_function_arguments_remain_unmodified_until_dispatch():
    call = ToolCall(call_id="call", name="lookup", arguments="{unfinished")
    assert json.loads(call.model_dump_json())["arguments"] == "{unfinished"
    with pytest.raises(ValidationError):
        FunctionCallOutput(output="Missing call ID")


@pytest.mark.parametrize(
    "create",
    [
        lambda: ModelRequest(messages=[]),
        lambda: ModelMessage(role="user", text="old shape"),
        lambda: ModelMessage(role="tool", content="Unmatched output"),
        lambda: ToolCall(call_id="call", name="lookup", arguments={}),
        lambda: ToolDefinition(
            name="lookup", description="Find", input_schema={}
        ),
        lambda: ModelRequest(input=[{"type": "unknown_provider_item"}]),
    ],
)
def test_old_and_unsupported_model_shapes_are_rejected(create):
    with pytest.raises(ValidationError):
        create()


def test_tool_definition_uses_explicit_responses_fields_and_strict_default():
    tool = ToolDefinition(
        name="lookup", description="Find", parameters=PARAMETERS
    )
    assert json.loads(tool.model_dump_json()) == {
        "type": "function",
        "name": "lookup",
        "description": "Find",
        "parameters": PARAMETERS,
        "strict": True,
    }
    with pytest.raises(ValidationError):
        ModelRequest(input=(), tools=(tool, tool))


@pytest.mark.parametrize(
    "parameters",
    [
        {"type": "array", "items": {"type": "string"}},
        {"type": "object", "properties": {}, "required": []},
        {**PARAMETERS, "required": []},
        {**PARAMETERS, "required": ["query", "query"]},
        {**PARAMETERS, "additionalProperties": {"type": "string"}},
        {**PARAMETERS, "properties": {"query": {"type": "object"}}},
        {
            **PARAMETERS,
            "properties": {
                "query": {"type": "array", "items": {"type": "object"}}
            },
        },
        {
            **PARAMETERS,
            "properties": {
                "query": {"anyOf": [{"type": "null"}, {"type": "object"}]}
            },
        },
        {**PARAMETERS, "$defs": {"Bad": {"type": "object"}}},
        {**PARAMETERS, "properties": {"query": {"$ref": "#/missing"}}},
        {
            **PARAMETERS,
            "properties": {
                "query": {"$ref": "https://example.invalid/schema"}
            },
        },
    ],
)
def test_strict_schemas_reject_open_or_optional_nested_objects(parameters):
    with pytest.raises(ValidationError):
        ToolDefinition(
            name="lookup", description="Find", parameters=parameters
        )


def test_strict_schemas_support_nullable_fields_references_and_literal_data():
    parameters = deepcopy(PARAMETERS)
    parameters["properties"]["query"] = {
        "anyOf": [{"type": "null"}, {"$ref": "#/$defs/Filter"}]
    }
    parameters["$defs"] = {
        "Filter": {
            "type": "object",
            "properties": {"next": {"$ref": "#/$defs/Filter"}},
            "required": ["next"],
            "additionalProperties": False,
        }
    }
    parameters["examples"] = [{"type": "object", "properties": "literal data"}]
    parameters["default"] = None
    tool = ToolDefinition(
        name="lookup", description="Find", parameters=parameters
    )
    assert json.loads(tool.model_dump_json())["parameters"] == parameters


def test_non_strict_schemas_require_an_explicit_opt_out():
    parameters = {
        "type": "object",
        "properties": {"query": {"type": "string"}},
    }
    tool = ToolDefinition(
        name="lookup", description="Find", parameters=parameters, strict=False
    )
    assert json.loads(tool.model_dump_json())["strict"] is False
    with pytest.raises(ValidationError):
        ToolDefinition(
            name="lookup", description="Find", parameters=parameters
        )
    with pytest.raises(ValidationError):
        ToolDefinition(
            name="lookup",
            description="Find",
            parameters=PARAMETERS,
            strict="false",
        )


def test_strict_schemas_accept_pydantic_recursive_object_definitions():
    class Filter(ContractModel):
        term: str
        next: Self | None

    parameters = Filter.model_json_schema()
    tool = ToolDefinition(
        name="lookup", description="Find", parameters=parameters
    )
    assert json.loads(tool.model_dump_json())["parameters"] == parameters


@pytest.mark.parametrize("strict", [True, False])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_parameter_schemas_reject_nonfinite_json(strict, value):
    with pytest.raises(ValidationError):
        ToolDefinition(
            name="lookup",
            description="Find",
            parameters={**PARAMETERS, "default": value},
            strict=strict,
        )
