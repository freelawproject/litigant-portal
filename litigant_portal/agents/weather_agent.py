import time

from litigant_portal.agents.base import Agent, Field, Tool, ToolOutput


class GetWeather(Tool):
    """Get the current weather for a location."""

    location: str = Field(
        description="The city or location to get the weather for."
    )

    def __call__(self, agent: "Agent") -> ToolOutput:
        time.sleep(5)
        return ToolOutput(
            response=(
                f"The weather in {self.location} is 72 degrees Fahrenheit."
            ),
            data={
                "location": self.location,
                "temp_f": 72,
                "unit": "fahrenheit",
            },
        )


class WeatherAgent(Agent):
    name = "weather-agent"
    tool_classes = [GetWeather]

    def load_system_prompt(self) -> str:
        return (
            "You are a friendly weather assistant. When the user asks about "
            "the weather, call the GetWeather tool with the location they "
            "mention, then summarize the result in a short, conversational "
            "reply."
        )
