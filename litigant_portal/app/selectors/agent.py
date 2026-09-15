"""
Database-backed configuration choices for the new agent's development page.
"""

from asgiref.sync import async_to_sync

from lp_agent.adapters.conversations import scope_choices
from lp_agent.preparation import CourtChoice as Court


def agent_scope_choices() -> tuple[Court, ...]:
    """
    Use the same enabled court/topic catalog as the agent's static flow.
    """
    return async_to_sync(scope_choices)()
