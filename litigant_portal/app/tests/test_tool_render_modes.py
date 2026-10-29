"""How the chat engine renders a tool call or result when no template says
otherwise.

A tool without a template, and a tool name the agent doesn't have, used to
fall back to a JSON box of the raw args and result data, shown to every user.
Both now render nothing.
"""

import json

from litigant_portal.agents.base import Tool
from litigant_portal.app.services.chat_engine import _render_tool, _tool_item


def _stored_call(name):
    return {
        "id": "call_1",
        "function": {"name": name, "arguments": json.dumps({"a": 1})},
    }


def test_a_tool_without_a_template_renders_nothing():
    assert _render_tool(None, {"args": {}}) == {"render_mode": "skip"}


def test_an_unknown_tool_renders_nothing():
    item = _tool_item(_stored_call("NoSuchTool"), results={}, tools={})

    assert item["call_render_mode"] == "skip"
    assert item["result_render_mode"] == "skip"


class _CardAfterReply(Tool):
    render_after_reply = True


def test_a_reloaded_tool_says_whether_its_card_follows_the_reply():
    # The chat moves an after-reply card below the turn's text (#1091), so a
    # reloaded thread needs the same flag the live stream sends.
    tools = {"_CardAfterReply": _CardAfterReply, "Plain": Tool}

    deferred = _tool_item(
        _stored_call("_CardAfterReply"), results={}, tools=tools
    )
    plain = _tool_item(_stored_call("Plain"), results={}, tools=tools)
    unknown = _tool_item(_stored_call("NoSuchTool"), results={}, tools={})

    assert deferred["after_reply"] is True
    assert plain["after_reply"] is False
    assert unknown["after_reply"] is False
