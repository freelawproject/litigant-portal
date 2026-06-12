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
with no registered handler) and fails fast. The ``ics`` and ``vcf`` handlers
format their data from a shared resolver (``resolve_ics_deadlines`` /
``resolve_vcf_contacts``) that their download handlers (downloads.py) also
consume, so what's downloaded can't drift from what's rendered on the page.
"""

from dataclasses import dataclass

from litigant_portal.app.topic_flow.contacts import resolve_vcf_contacts
from litigant_portal.app.topic_flow.deadlines import resolve_ics_deadlines
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


def submitted_section_anchor(corpus, submitted_ids):
    """Anchor id of the fact_gather section a set of submitted answers came from.

    The entry view redirects (PRG) back to this anchor so saving answers returns
    the litigant to the form they were filling — and to the deadlines that
    recompute just below it — rather than the top of the page. Matched on
    question-id overlap, so it stays correct with multiple fact_gather sections;
    returns ``None`` when nothing matches, leaving the redirect bare (page top).
    """
    submitted = set(submitted_ids)
    for section in corpus.sections:
        if isinstance(section, FactGatherSection) and any(
            question.id in submitted for question in section.questions
        ):
            return section.id
    return None


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

    The day is interpolated as ``value.day`` rather than via strftime's ``%-d``.
    ``%-d`` (no-leading-zero day) is a glibc/BSD extension, not standard C, so it
    raises ``ValueError`` on platforms whose C library lacks it — notably Windows
    — which would crash deadline rendering for a partner self-hosting LP there
    (#526). Weekday/month stay on strftime: ``%A``/``%B`` are standard and
    portable.
    """
    return f"{value.strftime('%A, %B')} {value.day}, {value.year}"


def _deadline_display(resolved):
    """Add page-display date strings to a resolved deadline.

    ``date_display``/``date_iso`` are ``None`` when the computed ``date`` is
    ``None`` (source answer absent or unparseable) — the "fill the date first"
    state — so the template shows the label without a date rather than erroring.
    ``date_iso`` feeds the ``<time>`` element; the ``.ics`` export consumes the
    same ``resolve_ics_deadlines`` output one layer up, so the two can't drift.
    """
    computed = resolved["date"]
    return {
        "label": resolved["label"],
        "description": resolved["description"],
        "date_display": _format_deadline_date(computed) if computed else None,
        "date_iso": computed.isoformat() if computed else None,
    }


@renderer("ics")
def _render_ics(section, corpus, answers):
    deadlines = [
        _deadline_display(resolved)
        for resolved in resolve_ics_deadlines(section, corpus, answers)
    ]
    meta = corpus.metadata
    # URL parts (not a built URL) so the template owns {% url %} resolution and
    # the renderer stays Django-free. ``has_dates`` gates the download link:
    # an empty calendar is no use, so the button only shows once at least one
    # deadline has a computed date.
    return RenderedSection(
        anchor_id=section.id,
        heading=section.heading,
        template=f"{_TEMPLATE_DIR}/flow_section_ics.html",
        context={
            "deadlines": deadlines,
            "has_dates": any(d["date_iso"] for d in deadlines),
            "court": meta.court,
            "topic": meta.topic,
            "role": meta.role,
            "output_id": section.id,
        },
    )


@renderer("vcf")
def _render_vcf(section, corpus, answers):
    contacts = resolve_vcf_contacts(section, corpus)
    meta = corpus.metadata
    # Same shape as _render_ics: the flat contact dicts are template-ready, and
    # the URL parts let the template own {% url %} resolution (renderer stays
    # Django-free). No gate like ics's has_dates — contacts are static corpus
    # data that always resolve (contact_ids is non-empty), so the download link
    # always shows.
    return RenderedSection(
        anchor_id=section.id,
        heading=section.heading,
        template=f"{_TEMPLATE_DIR}/flow_section_vcf.html",
        context={
            "contacts": contacts,
            "court": meta.court,
            "topic": meta.topic,
            "role": meta.role,
            "output_id": section.id,
        },
    )
