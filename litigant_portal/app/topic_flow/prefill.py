"""The variables a flow hands to its docassemble interview.

Pure, like the renderer: the reviewed-only answer read happens at the call
site, these functions only resolve the corpus mapping and rename what it holds.
"""

from urllib.parse import parse_qs, urlparse

from litigant_portal.app.topic_flow.schema import PacketOutput


def interview_reference(section) -> str | None:
    """The interview reference a packet section hands off to, or None.

    Extracted from the launch URL's ``?i=`` parameter; the host around it is
    never used (#879). The URL parse goes away when the corpus carries the
    bare reference.
    """
    if not isinstance(section, PacketOutput) or not section.interview_url:
        return None
    references = parse_qs(urlparse(section.interview_url).query).get("i", [])
    return references[0] if references else None


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
