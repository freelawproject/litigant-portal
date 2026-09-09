import json
from copy import deepcopy

import pytest
from pydantic import ValidationError

from lp_agent.types import ModelMessage, ModelRequest, ToolDefinition
from lp_agent.utils.audit import InstructionArtifact

TOOL = {
    "name": "lookup",
    "description": "Find guidance",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False,
    },
}
GOLDEN_JSON = (
    '{"format":"lp_agent.instructions.v1","instructions":" Help café\\n",'
    '"tools":[{"description":"Find guidance","name":"lookup","parameters":'
    '{"additionalProperties":false,"properties":{},"required":[],"type":"object"},'
    '"strict":true,"type":"function"}]}'
)
GOLDEN_HASH = (
    "9c8586107696585a34694550cf5bf5943dc692f874eee7504e847dd774e163fe"
)


def artifact(*, instructions=" Help café\n", tools=None):
    return InstructionArtifact(
        instructions=instructions,
        tools=[TOOL] if tools is None else tools,
    )


def test_version_one_canonical_bytes_and_hash_are_fixed():
    original = artifact()
    assert original.canonical_bytes() == GOLDEN_JSON.encode("utf-8")
    assert original.content_hash() == GOLDEN_HASH
    restored = InstructionArtifact.model_validate_json(
        original.canonical_bytes()
    )
    assert restored.content_hash() == GOLDEN_HASH


def test_key_order_and_explicit_defaults_do_not_change_fingerprint():
    reordered = dict(reversed(TOOL.items()))
    reordered["parameters"] = dict(reversed(TOOL["parameters"].items()))
    reordered.update(strict=True, type="function")
    assert artifact(tools=[reordered]).content_hash() == GOLDEN_HASH


@pytest.mark.parametrize(
    "instructions", ["Help café\n", " Help café", " Help cafe\n"]
)
def test_instruction_whitespace_and_unicode_are_significant(instructions):
    assert artifact(instructions=instructions).content_hash() != GOLDEN_HASH


@pytest.mark.parametrize(
    "change",
    [
        {"name": "another_lookup"},
        {"description": "Find different guidance"},
        {"strict": False},
        {"parameters": {**TOOL["parameters"], "description": "New arguments"}},
    ],
)
def test_instruction_or_tool_changes_change_fingerprint(change):
    assert artifact(tools=[{**TOOL, **change}]).content_hash() != GOLDEN_HASH


def test_tool_and_schema_array_order_is_preserved():
    other = {**TOOL, "name": "other"}
    assert (
        artifact(tools=[TOOL, other]).content_hash()
        != artifact(tools=[other, TOOL]).content_hash()
    )
    parameters = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"a": {"type": "string"}, "b": {"type": "string"}},
        "required": ["a", "b"],
    }
    reordered = {**parameters, "required": ["b", "a"]}
    assert (
        artifact(tools=[{**TOOL, "parameters": parameters}]).content_hash()
        != artifact(tools=[{**TOOL, "parameters": reordered}]).content_hash()
    )


def test_request_snapshot_excludes_history_and_copies_mutable_schemas():
    tool = ToolDefinition(**deepcopy(TOOL))
    request = ModelRequest(
        instructions=" Help café\n",
        tools=(tool,),
        input=(ModelMessage(role="user", content="Private user message"),),
    )
    snapshot = InstructionArtifact.from_request(request)
    assert snapshot.content_hash() == GOLDEN_HASH
    assert "Private user message" not in snapshot.canonical_bytes().decode()
    tool.parameters["description"] = "Changed after snapshot"
    assert snapshot.content_hash() == GOLDEN_HASH
    assert (
        InstructionArtifact.from_request(request).content_hash() != GOLDEN_HASH
    )


def test_unknown_format_cannot_be_read_as_version_one():
    payload = json.loads(GOLDEN_JSON)
    payload["format"] = "lp_agent.instructions.v2"
    with pytest.raises(ValidationError):
        InstructionArtifact.model_validate(payload)


def test_canonicalization_rejects_nonfinite_numbers_even_after_mutation():
    original = artifact()
    original.tools[0].parameters["default"] = float("nan")
    with pytest.raises(ValueError):
        original.canonical_bytes()
