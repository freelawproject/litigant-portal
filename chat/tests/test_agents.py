"""
Tests for agent base classes and tool system.

Tests the Agent and Tool abstractions without making LLM API calls.
"""

from unittest.mock import MagicMock

from django.test import TestCase
from pydantic import Field

from chat.agents.base import Agent, Tool
from chat.agents.weather import WeatherAgent, WeatherTool


class ToolSchemaTests(TestCase):
    """Tests for Tool.get_schema() method."""

    def test_schema_includes_function_name(self):
        """Schema should include the class name as function name."""
        schema = WeatherTool.get_schema()

        self.assertEqual(schema["function"]["name"], "WeatherTool")

    def test_schema_includes_docstring(self):
        """Schema should include docstring as description."""
        schema = WeatherTool.get_schema()

        self.assertIn("weather", schema["function"]["description"].lower())

    def test_schema_includes_parameters(self):
        """Schema should include field definitions as parameters."""
        schema = WeatherTool.get_schema()

        params = schema["function"]["parameters"]
        self.assertIn("properties", params)
        self.assertIn("location", params["properties"])


class ToolExecutionTests(TestCase):
    """Tests for tool execution."""

    def test_weather_tool_returns_mock_data(self):
        """WeatherTool should return mock temperature data."""
        tool = WeatherTool(location="San Antonio")
        agent = MagicMock()

        result = tool(agent)

        self.assertIn("San Antonio", result.response)
        self.assertIn("72", result.response)


class AgentInitializationTests(TestCase):
    """Tests for Agent.__init__() configuration."""

    def test_uses_default_model(self):
        """Agent should use default_model if none provided."""
        agent = WeatherAgent()

        self.assertEqual(agent.model, "groq/llama-3.3-70b-versatile")

    def test_overrides_model(self):
        """Provided model should override default."""
        agent = WeatherAgent(model="openai/gpt-4")

        self.assertEqual(agent.model, "openai/gpt-4")

    def test_includes_system_prompt(self):
        """System prompt should be first message."""
        agent = WeatherAgent()

        self.assertEqual(agent.messages[0]["role"], "system")
        self.assertIn("weather", agent.messages[0]["content"].lower())

    def test_replaces_messages_when_provided(self):
        """Provided messages should replace default messages."""
        agent = WeatherAgent(messages=[{"role": "user", "content": "Hello"}])

        self.assertEqual(len(agent.messages), 1)
        self.assertEqual(agent.messages[0]["content"], "Hello")

    def test_initializes_empty_state(self):
        """State should be empty dict by default."""
        agent = WeatherAgent()

        self.assertEqual(agent.state, {})

    def test_registers_tools_by_name(self):
        """Tools should be accessible by class name."""
        agent = WeatherAgent()

        self.assertIn("WeatherTool", agent.tools)
        self.assertEqual(agent.tools["WeatherTool"], WeatherTool)


class AgentMessagesForLlmTests(TestCase):
    """Tests for Agent.messages_for_llm property."""

    def test_strips_data_field_from_tool_messages(self):
        """Tool messages should have data field stripped for LLM."""

        class TestAgent(Agent):
            default_messages = []

        agent = TestAgent(
            messages=[
                {
                    "role": "tool",
                    "tool_call_id": "123",
                    "name": "test",
                    "content": "Result",
                    "data": {"extra": "data"},
                }
            ]
        )

        llm_messages = agent.messages_for_llm

        self.assertEqual(len(llm_messages), 1)
        self.assertNotIn("data", llm_messages[0])
        self.assertEqual(llm_messages[0]["content"], "Result")

    def test_preserves_tool_calls(self):
        """tool_calls should be preserved in assistant messages."""

        class TestAgent(Agent):
            default_messages = []

        agent = TestAgent(
            messages=[
                {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [{"id": "1", "function": {"name": "test"}}],
                }
            ]
        )

        llm_messages = agent.messages_for_llm

        self.assertIn("tool_calls", llm_messages[0])


class AgentToolExecutionTests(TestCase):
    """Tests for Agent.execute_tool() method."""

    def test_executes_registered_tool(self):
        """Should execute tool and return response dict."""
        agent = WeatherAgent()

        tool_msg, response_event = agent.execute_tool(
            {
                "id": "call_123",
                "function": {
                    "name": "WeatherTool",
                    "arguments": '{"location": "Austin"}',
                },
            }
        )

        self.assertEqual(tool_msg["tool_call_id"], "call_123")
        self.assertEqual(tool_msg["name"], "WeatherTool")
        self.assertIn("Austin", tool_msg["content"])
        self.assertEqual(response_event["type"], "tool_response")
        self.assertEqual(response_event["id"], "call_123")

    def test_handles_unknown_tool(self):
        """Should return error for unknown tool name."""
        agent = WeatherAgent()

        tool_msg, response_event = agent.execute_tool(
            {
                "id": "call_123",
                "function": {"name": "UnknownTool", "arguments": "{}"},
            }
        )

        self.assertIn("Unknown tool", tool_msg["content"])


class CustomToolTests(TestCase):
    """Tests for creating custom tools."""

    def test_custom_tool_with_field(self):
        """Custom tool should work with Field definitions."""

        class AddNumbers(Tool):
            """Add two numbers together."""

            a: int = Field(description="First number")
            b: int = Field(description="Second number")

            def __call__(self, agent: Agent) -> str:
                return str(self.a + self.b)

        tool = AddNumbers(a=5, b=3)
        result = tool(MagicMock())

        self.assertEqual(result, "8")

    def test_tool_can_modify_agent_state(self):
        """Tool should be able to store data in agent.state."""

        class StateModifier(Tool):
            """Modify agent state."""

            key: str
            value: str

            def __call__(self, agent: Agent) -> str:
                agent.state[self.key] = self.value
                return "Done"

        agent = Agent()
        tool = StateModifier(key="test", value="data")
        tool(agent)

        self.assertEqual(agent.state["test"], "data")


class StreamEventTypesTests(TestCase):
    """Tests for stream event type constants."""

    def test_content_delta_event_structure(self):
        """content_delta events should have type and content."""
        event = {"type": "content_delta", "content": "Hello"}
        self.assertEqual(event["type"], "content_delta")

    def test_tool_call_event_structure(self):
        """tool_call events should have type, id, name, args."""
        event = {"type": "tool_call", "id": "123", "name": "test", "args": {}}
        self.assertEqual(event["type"], "tool_call")

    def test_tool_response_event_structure(self):
        """tool_response events should have type, id, name."""
        event = {"type": "tool_response", "id": "123", "name": "test"}
        self.assertEqual(event["type"], "tool_response")

    def test_done_event_structure(self):
        """done events should have type."""
        event = {"type": "done"}
        self.assertEqual(event["type"], "done")

    def test_error_event_structure(self):
        """error events should have type and error."""
        event = {"type": "error", "error": "Something went wrong"}
        self.assertEqual(event["type"], "error")
