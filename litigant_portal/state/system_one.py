"""
No-op placeholders for optional System One reduction and projection.

These accept the planned inputs but produce no result. Application callers
continue to use the Python reducer and projector.
"""

from datetime import date

from litigant_portal.state.types import ActionType, CourtRulesType, StateType


def reduce(current_state: StateType, action: ActionType) -> None:
    """
    Reserve the model reduction boundary without changing state.
    """


def project(
    state: StateType,
    court_rules: CourtRulesType,
    time_context: date,
    limit: int = 1,
) -> None:
    """
    Reserve the model projection boundary without producing guidance.
    """
