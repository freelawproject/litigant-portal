from django.utils import timezone

from .base import Agent, AgentState
from .tools.check_weather import CheckWeather


class WeatherState(AgentState):
    """What the weather agent remembers across a thread."""

    recent_locations: list[str] = []


class WeatherAgent(Agent):
    """A demo agent that can check the weather."""

    completion_args = {"max_tokens": 1000}
    state_schema = WeatherState
    tools = [CheckWeather]

    def generate_system_prompt(self, *, thread_id) -> str:
        from litigant_portal.app.models import ChatThread

        thread = ChatThread.objects.get(id=thread_id)
        state = WeatherState.model_validate(thread.state or {})
        now = timezone.localtime().strftime("%A, %B %-d, %Y at %-I:%M %p")
        recent = ", ".join(state.recent_locations) or "none yet"
        return (
            "You are a friendly weather assistant.\n"
            f"The current date and time is {now}.\n"
            f"Recently checked locations: {recent}.\n"
            "If the user asks about the weather for a location, use the "
            "CheckWeather tool. If they ask about a location you've already "
            "checked recently, you may report it from memory instead."
        )
