"""The variables a flow hands to its docassemble interview.

Pure: the reviewed-only answer read happens at the call site, these
functions only resolve the mapping from the TopicFlow row and rename what it
holds.
"""


def flow_interview_target(flow) -> tuple[str, dict] | None:
    """``(flow.interview_reference, flow.interview_prefill)``, or None when
    the row has no reference."""
    if not flow.interview_reference:
        return None
    return flow.interview_reference, dict(flow.interview_prefill)


def prefill_variables(*, mapping: dict, answers: dict) -> dict:
    """``{interview variable: value}`` for the mapped answers we hold.

    An unanswered question is absent rather than blank, so the interview asks
    it. Values pass through untouched: a stored date is already the ISO string
    docassemble parses back into a date object.
    """
    return {
        variable: answers[question_id]
        for question_id, variable in mapping.items()
        if question_id in answers
    }
