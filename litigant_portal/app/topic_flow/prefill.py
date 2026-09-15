"""The variables a flow hands to its docassemble interview.

Pure, like the renderer: the reviewed-only answer read happens at the call
site, these functions only resolve the corpus mapping and rename what it holds.
"""

from litigant_portal.app.topic_flow.schema import PacketOutput


def interview_target(corpus) -> tuple[str, dict] | None:
    """``(launch url, {question id: interview variable})``, or None.

    The first packet section carrying an interview_url wins; a corpus with no
    interview handoff returns None.
    """
    for section in corpus.sections:
        if isinstance(section, PacketOutput) and section.interview_url:
            return section.interview_url, dict(section.interview_prefill)
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
