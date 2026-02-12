from .base import Agent, Field, Tool, ToolOutput


class WeatherTool(Tool):
    """Get the current weather for a location."""

    location: str = Field(
        description="City name or location to get weather for"
    )

    def __call__(self, agent: Agent) -> ToolOutput:
        """Return mock weather data for the location."""
        temp_f = 72
        condition = "sunny"

        return ToolOutput(
            # This is what the LLM sees
            response=f"Location: {self.location}, Temp: {temp_f} F, Condition: {condition}.",
            # This is structured data for the frontend
            data={
                "location": self.location,
                "temp_f": temp_f,
                "condition": condition,
            },
        )


class WeatherAgent(Agent):
    """A demo agent that can check the weather.

    This is a test agent to verify the agent framework is working correctly.
    """

    default_model = "groq/llama-3.3-70b-versatile"
    default_tools = [WeatherTool]
    default_messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. If the user asks about the weather, "
                "use the WeatherTool to get current conditions. Be concise."
            ),
        }
    ]
    default_completion_args = {
        "max_tokens": 1024,
    }
