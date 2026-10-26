import json
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


def test_uploaded_evidence_remains_native_content():
    image = {
        "type": "image_url",
        "image_url": {"url": "data:image/png;base64,aA=="},
    }
    context = {"messages": [{"role": "user", "content": [image]}]}
    content = AgentJudge.request(context, "The notice says Friday.")[1][
        "content"
    ]
    assert content[1] == image
    assert "base64" not in content[0]["text"]
    assert context["messages"][0]["content"] == [image]


@pytest.mark.parametrize("fence", ["", "```", "```json", "```JSON"])
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
        content = f"{fence}\n{content}\n```"
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
