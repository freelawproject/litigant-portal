import json
from copy import deepcopy
from types import SimpleNamespace

import pytest

from litigant_portal.agents.judge import AgentJudge, JudgeVerdict


def response(content, *, finish_reason="stop", tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                finish_reason=finish_reason,
                message=SimpleNamespace(
                    content=content, tool_calls=tool_calls
                ),
            )
        ]
    )


def test_request_and_valid_verdicts():
    context = {"messages": [{"role": "user", "content": "Help me file."}]}
    messages = AgentJudge.request(context, "Bring the form.")
    assert json.loads(messages[1]["content"]) == {
        **context,
        "candidate": "Bring the form.",
    }
    for approved, findings in (
        (True, []),
        (False, [{"code": "unsupported_claim", "message": "Remove the fee."}]),
    ):
        payload = {"approved": approved, "findings": findings}
        verdict = AgentJudge.review(response(json.dumps(payload)))
        assert verdict.model_dump(mode="json") == payload


@pytest.mark.parametrize(
    "attachment",
    [
        {
            "type": "image_url",
            "image_url": {"url": "data:image/png;base64,aA=="},
        },
        {
            "type": "file",
            "file": {
                "file_data": "data:application/pdf;base64,aA==",
                "filename": "notice.pdf",
            },
        },
        {"type": "file", "file": {"file_id": "file-example"}},
    ],
)
def test_request_excludes_native_attachments(attachment):
    text = {"type": "text", "text": "Please explain this notice."}
    context = {
        "messages": [
            {"role": "user", "content": [attachment]},
            {"role": "assistant", "content": "Earlier reply."},
            {"role": "user", "content": [text, attachment]},
            {
                "role": "tool",
                "tool_call_id": "load-source",
                "content": "Supplied procedural guidance.",
            },
        ],
        "state": {"name": "Alex"},
    }
    original = deepcopy(context)
    messages = AgentJudge.request(context, "Bring the form.")
    assert all(isinstance(message["content"], str) for message in messages)
    payload = json.loads(messages[1]["content"])
    marker = {
        "type": "text",
        "text": "[Attachment excluded from text-only review]",
    }
    assert payload == {
        **original,
        "candidate": "Bring the form.",
        "messages": [
            {"role": "user", "content": [marker]},
            original["messages"][1],
            {"role": "user", "content": [text, marker]},
            original["messages"][3],
        ],
    }
    assert context == original


@pytest.mark.parametrize(
    "fence", ["", "```", "```json", "```JSON", "```json \t"]
)
@pytest.mark.parametrize("approved", [False, True])
def test_verdict_whitespace_and_outer_fence(fence, approved):
    payload = {
        "approved": approved,
        "findings": (
            [] if approved else [{"code": "off_topic", "message": "Redirect."}]
        ),
    }
    content = json.dumps(payload)
    if fence:
        closing = " \t``` " if fence.endswith("\t") else "```"
        content = f"{fence}\n{content}\n{closing}"
    reply = response(f" \n{content}\n ")
    assert AgentJudge.review(reply).model_dump(mode="json") == payload
    assert reply.choices[0].message.content == f" \n{content}\n "


@pytest.mark.parametrize(
    "content",
    [
        'Here is the verdict: {"approved":true,"findings":[]}',
        '```json\n{"approved":true,"findings":[]}\n```\nCommentary',
        '```json\n{"approved":true,"findings":[]}',
        '```python\n{"approved":true,"findings":[]}\n```',
        '```\n```json\n{"approved":true,"findings":[]}\n```\n```',
        '```json\n{"approved":false,"findings":[]}\n```',
        "```json\nnot JSON\n```",
    ],
)
def test_verdict_does_not_extract_or_repair_json(content):
    with pytest.raises(ValueError):
        AgentJudge.review(response(content))


def test_correction_is_labeled_and_carries_findings():
    verdict = JudgeVerdict.model_validate(
        {
            "approved": False,
            "findings": [{"code": "off_topic", "message": "Redirect."}],
        }
    )
    message = AgentJudge.correction(verdict)
    assert message["role"] == "user"
    assert message["content"].startswith(
        "Internal review feedback, not a new user request."
    )
    assert json.loads(message["content"].split("Findings: ")[1]) == (
        verdict.model_dump(mode="json")
    )


@pytest.mark.parametrize(
    "payload",
    [
        {
            "approved": True,
            "findings": [{"code": "off_topic", "message": "x"}],
        },
        {"approved": False, "findings": []},
        {"approved": "true", "findings": []},
        {"approved": False, "findings": [{"code": "unknown", "message": "x"}]},
        {
            "approved": False,
            "findings": [{"code": "off_topic", "message": " "}],
        },
    ],
)
def test_invalid_verdicts(payload):
    with pytest.raises(ValueError):
        JudgeVerdict.model_validate(payload)


@pytest.mark.parametrize(
    "reply",
    [
        response("not JSON"),
        response(None),
        response('{"approved":true,"findings":[]}', finish_reason="length"),
        response('{"approved":true,"findings":[]}', tool_calls=[{}]),
    ],
)
def test_malformed_or_incomplete_responses(reply):
    with pytest.raises(ValueError):
        AgentJudge.review(reply)
