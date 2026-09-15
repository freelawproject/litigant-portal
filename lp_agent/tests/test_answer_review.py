"""
Answer review requires complete structured verdicts and concrete corpus evidence.
"""

import asyncio

import pytest

from lp_agent.demo.seed import preparation_prompt
from lp_agent.flows.judge import AgentJudge
from lp_agent.tests.helpers import ScriptedModel, answer_item
from lp_agent.types import ModelFinished, ModelOutputItem, ToolCall


@pytest.mark.parametrize(
    "events",
    [
        [answer_item('{"approved": true, "findings": []}')],
        [
            answer_item('{"approved": true, "findings": []}'),
            ModelFinished(reason="length"),
        ],
        [
            answer_item('{"approved": "true", "findings": []}'),
            ModelFinished(reason="stop"),
        ],
        [
            answer_item('{"approved": false, "findings": []}'),
            ModelFinished(reason="stop"),
        ],
        [
            answer_item(
                '{"approved": true, "findings": [{"code":"unsupported_claim", "message":"unsupported"}]}'
            ),
            ModelFinished(reason="stop"),
        ],
        [
            ModelOutputItem(
                item=ToolCall(
                    call_id="judge-call", name="save", arguments="{}"
                )
            ),
            ModelFinished(reason="tool_calls"),
        ],
    ],
)
def test_incomplete_or_invalid_judge_response_is_not_approval(events):
    model = ScriptedModel(events)
    request = AgentJudge.request(
        {"question": "What is the fee?", "material": {}}, "A claim"
    )
    with pytest.raises(ValueError):
        asyncio.run(AgentJudge.review(model, request))
    assert model.closed


def test_prompt_removes_only_legacy_handoff_and_preserves_later_law():
    text = """COURT CONTEXT
Applicable instructions.
GUIDED FLOW HANDOFF
Use the case panel.
LEGAL LIMITS
Retain publication and timing requirements.
HANDOFF TO THE GUIDED FLOW
Call an old UI tool.
COURT CONTACTS
Ask the clerk.
"""
    result = preparation_prompt(text)
    assert (
        "LEGAL LIMITS\nRetain publication and timing requirements." in result
    )
    assert "COURT CONTACTS\nAsk the clerk." in result
    assert "case panel" not in result
    assert "old UI tool" not in result
