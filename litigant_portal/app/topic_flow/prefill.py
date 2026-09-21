"""The variables a flow hands to its docassemble interview.

Pure, like the renderer: the reviewed-only answer read happens at the call
site, these functions only resolve the corpus mapping and rename what it holds.
"""

from litigant_portal.app.topic_flow.schema import PacketOutput


def interview_reference(section) -> str | None:
    """The interview reference a packet section hands off to, or None."""
    if isinstance(section, PacketOutput):
        return section.interview_reference
    return None


def interview_target(corpus) -> tuple[str, dict] | None:
    """``(interview reference, {question id: interview variable})``, or None.

    The first packet section carrying an interview wins; a corpus with no
    interview handoff returns None.
    """
    for section in corpus.sections:
        reference = interview_reference(section)
        if reference:
            return reference, dict(section.interview_prefill)
    return None


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
