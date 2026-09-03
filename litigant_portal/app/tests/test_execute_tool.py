"""Tests for _execute_tool's error normalization in the chat engine.

Every failure mode (unknown tool, invalid args, tool raising) must come back
as a ToolOutput error result — an exception escaping the tool loop would kill
the SSE stream mid-conversation. All tests are DB-free and run in the fast
suite.
"""

from litigant_portal.agents.base import Tool, ToolOutput
from litigant_portal.app.services.chat_engine import _execute_tool


class EchoTool(Tool):
    greeting: str

    def __call__(self, *, thread_id) -> ToolOutput:
        return ToolOutput(
            result=f"{self.greeting} on {thread_id}",
            render_data={"greeting": self.greeting},
            refresh_system_prompt=True,
            cost=0.25,
        )


class ExplodingTool(Tool):
    def __call__(self, *, thread_id) -> ToolOutput:
        raise RuntimeError("boom")


def test_unknown_tool_returns_error_output():
    output = _execute_tool(
        tool_class=None, args={}, thread_id="t1", name="NoSuchTool"
    )
    assert output.result == "Error: Unknown tool: NoSuchTool"


def test_invalid_args_return_error_output():
    output = _execute_tool(
        tool_class=EchoTool,
        args={"greeting": {"not": "a string"}},
        thread_id="t1",
        name="EchoTool",
    )
    assert output.result.startswith("Error: ")
    assert "greeting" in output.result


def test_extra_args_are_accepted_not_errors():
    # Pins Tool's extra="allow" (agents/base.py): a hallucinated argument
    # name is silently ignored, not normalized to an error. If extras
    # should be rejected instead, this test is the one to flip.
    output = _execute_tool(
        tool_class=EchoTool,
        args={"greeting": "hello", "made_up_arg": True},
        thread_id="t1",
        name="EchoTool",
    )
    assert output.result == "hello on t1"


def test_raising_tool_returns_error_output():
    output = _execute_tool(
        tool_class=ExplodingTool, args={}, thread_id="t1", name="ExplodingTool"
    )
    assert output.result == "Error: boom"


def test_successful_tool_output_passes_through():
    output = _execute_tool(
        tool_class=EchoTool,
        args={"greeting": "hello"},
        thread_id="t1",
        name="EchoTool",
    )
    assert output.result == "hello on t1"
    assert output.render_data == {"greeting": "hello"}
    assert output.refresh_system_prompt is True
    assert output.cost == 0.25


def test_error_output_keeps_toploop_defaults():
    output = _execute_tool(
        tool_class=ExplodingTool, args={}, thread_id="t1", name="ExplodingTool"
    )
    assert output.render_data is None
    assert output.refresh_system_prompt is False
    assert output.cost == 0.0
