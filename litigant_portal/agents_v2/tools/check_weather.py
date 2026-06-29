import time

from litigant_portal.agents_v2.base import Field, Tool, ToolOutput


class CheckWeather(Tool):
    """Check the current weather for a location."""

    location: str = Field(description="City or place to check the weather for")

    # While it's the last message, the call card shows a "checking weather"
    # spinner; the result card shows the location and temperature.
    tool_call_template = "tools/check_weather_call.html"
    tool_result_template = "tools/check_weather_result.html"

    def __call__(self, *, thread_id) -> ToolOutput:
        from litigant_portal.agents_v2.weather import WeatherState
        from litigant_portal.app.models import ChatThread

        # Artificial delay so the "checking weather" call card is visible.
        time.sleep(2)

        thread = ChatThread.objects.get(id=thread_id)
        state = WeatherState.model_validate(thread.state or {})
        if self.location not in state.recent_locations:
            state.recent_locations.append(self.location)
            thread.state = state.model_dump()
            thread.save(update_fields=["state", "updated_at"])

        temp_f = 72
        return ToolOutput(
            result=f"It is {temp_f} degrees in {self.location}.",
            render_data={"location": self.location, "temp_f": temp_f},
            # Surface the newly-checked location in the next system prompt.
            refresh_system_prompt=True,
        )
