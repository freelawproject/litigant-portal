from litigant_portal.agents.weather_agent import WeatherAgent

agents = [WeatherAgent]

agent_registry = {agent.name: agent for agent in agents}
