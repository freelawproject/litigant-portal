from litigant_portal.state.types import StateType


def request_interview(state: StateType, interview_reference: str) -> None:
    """
    Reserve the lifecycle handoff boundary without executing an operation.

    Phase 1 deliberately produces no session, result, or completion state.
    The existing user-initiated Docassemble launch remains separate.
    """
