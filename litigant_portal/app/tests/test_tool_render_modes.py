"""How the chat engine renders a tool call or result when no template says
otherwise.

A tool without a template, and a tool name the agent doesn't have, used to
fall back to a JSON box of the raw args and result data, shown to every user.
Both now render nothing.
"""

import json

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
