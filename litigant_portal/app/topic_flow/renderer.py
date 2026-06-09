"""Registry dispatch of corpus sections to render context.

Turns each validated corpus ``Section`` into a ``RenderedSection`` — a template
path plus a flat, fully-resolved context dict — so the page view stays
orchestration-only and templates stay logic-free. All section-type dispatch
(``kind``, and ``output_type`` for outputs) is confined to the registry here;
nothing downstream branches on section type.

The renderer is *fat* but *pure*: it takes the ``corpus`` and a plain
``answers`` dict (e.g. from ``AnswerStore.all()``) and resolves everything the
template needs — prefilled fields, answer labels, form lists. It imports no
session/request machinery.

Corpus validity is guaranteed upstream at load, so the renderer never
re-validates data; an unhandled section type is a *code* gap (a union member
with no registered handler) and fails fast. The ``ics`` handler renders its
deadline list here (its first caller of ``compute_deadline``); the ``.ics``
download button and the ``vcf`` handler land with their download-view item, so
rendering a ``vcf`` still raises.
"""

from dataclasses import dataclass

from litigant_portal.app.topic_flow.deadlines import compute_deadline
from litigant_portal.app.topic_flow.schema import FactGatherSection


@dataclass(frozen=True)
class RenderedSection:
    anchor_id: str
    heading: str
    template: str
    context: dict


# Dispatch key (``kind``, or ``output_type`` for outputs) -> handler.
SECTION_RENDERERS = {}

_TEMPLATE_DIR = "cotton/molecules"


def renderer(key):
    """Register a handler under its dispatch key. Used as a decorator."""

    def register(fn):
        SECTION_RENDERERS[key] = fn
        return fn

    return register


def _dispatch_key(section):
    # Output sections share kind="output" and discriminate on output_type;
    # everything else dispatches on kind. The two value spaces don't collide.
    return getattr(section, "output_type", None) or section.kind


def render_section(section, corpus, answers):
    """Render one section to a ``RenderedSection``, or raise if unhandled."""
    key = _dispatch_key(section)
    handler = SECTION_RENDERERS.get(key)
    if handler is None:
        raise ValueError(f"No SectionRenderer handler registered for {key!r}")
    return handler(section, corpus, answers)


@renderer("info")
def _render_info(section, corpus, answers):
    return RenderedSection(
        anchor_id=section.id,
        heading=section.heading,
        template=f"{_TEMPLATE_DIR}/flow_section_info.html",
        context={"body": section.body},
    )


@renderer("fact_gather")
def _render_fact_gather(section, corpus, answers):
    questions = [
        {
            "id": q.id,
            "label": q.label,
            "type": q.type,
            "required": q.required,
            "choices": q.choices,
            "help_text": q.help_text,
            "value": answers.get(q.id, ""),
        }
        for q in section.questions
    ]
    return RenderedSection(
        anchor_id=section.id,
        heading=section.heading or "",
        template=f"{_TEMPLATE_DIR}/flow_section_fact_gather.html",
        context={"questions": questions},
    )


def _fact_gather_questions(corpus):
    """Yield every fact_gather Question, in corpus order.

    The single walk over the section union; ``question_ids`` and the summary
    builder both consume it, so the ``isinstance`` dispatch lives in one place,
    confined to the renderer rather than leaking into the view.
    """
    for section in corpus.sections:
        if isinstance(section, FactGatherSection):
            yield from section.questions


def question_ids(corpus):
    """All fact_gather question ids, in corpus order.

    The set of POST keys the entry view accepts — everything else (csrf token,
    stray keys) is ignored.
    """
    return [question.id for question in _fact_gather_questions(corpus)]


def _answered_in_corpus_order(corpus, answers):
    """Yield ``{label, value}`` for answered questions, in corpus order."""
    for question in _fact_gather_questions(corpus):
        if question.id in answers:
            yield {"label": question.label, "value": answers[question.id]}


@renderer("summary")
def _render_summary(section, corpus, answers):
    return RenderedSection(
        anchor_id=section.id,
        heading=section.heading,
        template=f"{_TEMPLATE_DIR}/flow_section_summary.html",
        context={"items": list(_answered_in_corpus_order(corpus, answers))},
    )


@renderer("packet")
def _render_packet(section, corpus, answers):
    return RenderedSection(
        anchor_id=section.id,
        heading=section.heading,
        template=f"{_TEMPLATE_DIR}/flow_section_packet.html",
        context={"forms": list(section.forms)},
    )


def _format_deadline_date(value):
    """Human-readable deadline date, e.g. "Tuesday, March 3, 2026".

    ``%-d`` drops the leading zero (POSIX; the app runs on Linux/macOS).
    """
    return value.strftime("%A, %B %-d, %Y")


def _deadline_context(deadline, answers):
    """Flat, template-ready view of one deadline computed from ``answers``.

    ``date_display``/``date_iso`` are ``None`` when the source answer is absent
    or unparseable — the "fill the date first" state — so the template shows the
    label without a date rather than erroring. ``date_iso`` feeds the ``<time>``
    element now and the ``.ics`` export later (#441).
    """
    computed = compute_deadline(deadline, answers)
    return {
        "label": deadline.label,
        "description": deadline.description,
        "date_display": _format_deadline_date(computed) if computed else None,
        "date_iso": computed.isoformat() if computed else None,
    }


@renderer("ics")
def _render_ics(section, corpus, answers):
    # Resolve the section's deadline_ids against corpus-level deadlines, in the
    # section's declared order. The loader guarantees every id resolves, so the
    # lookup never misses for a valid corpus.
    by_id = {deadline.id: deadline for deadline in corpus.deadlines}
    deadlines = [
        _deadline_context(by_id[did], answers) for did in section.deadline_ids
    ]
    return RenderedSection(
        anchor_id=section.id,
        heading=section.heading,
        template=f"{_TEMPLATE_DIR}/flow_section_ics.html",
        context={"deadlines": deadlines},
    )
