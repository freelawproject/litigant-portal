"""Deadline math for Topic Flow.

A corpus ``Deadline`` is an ``offset_days`` from a gathered date — e.g. "30 days
after the notice was published". This module turns that relative definition plus
the user's answers into a concrete ``date``.

Pure and AI-free, mirroring ``renderer.py``: no session/request machinery, no
corpus re-validation (validity is guaranteed upstream at load). The one thing it
guards is *user* input — an absent or malformed date yields ``None`` (the
"fill the date first" state), never an exception.

``deadline_date`` and ``deadline_display`` are the halves both paths share:
the content path keys a deadline by its question id, the rows path
(``rows.py``) by its ``offset_from`` variable's name.
"""

from datetime import date, timedelta

from litigant_portal.app.formatting import format_long_date


def deadline_date(offset_days, source_name, answers):
    """``answers[source_name]`` (an ISO ``YYYY-MM-DD`` string) plus
    ``offset_days``, or ``None`` when that answer is absent, blank, or not a
    parseable date — a half-filled form is normal, not an error."""
    raw = answers.get(source_name)
    if not raw:
        return None
    try:
        gathered = date.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    return gathered + timedelta(days=offset_days)


def compute_deadline(deadline, answers):
    """Return ``deadline``'s date from ``answers``, or ``None`` if uncomputable.

    Reads the answer to ``deadline.offset_from`` (a ``date`` question) and
    adds ``offset_days``; see ``deadline_date``.
    """
    return deadline_date(deadline.offset_days, deadline.offset_from, answers)


def deadline_display(resolved):
    """Add page-display date strings to a resolved deadline.

    ``date_display``/``date_iso`` are ``None`` when the computed ``date`` is
    ``None`` (source answer absent or unparseable) — the "fill the date first"
    state — so the template shows the label without a date rather than erroring.
    ``date_iso`` feeds the ``<time>`` element; the ``.ics`` export consumes the
    same resolved dicts one layer up, so the two can't drift.
    """
    computed = resolved["date"]
    return {
        "label": resolved["label"],
        "description": resolved["description"],
        "date_display": format_long_date(computed) if computed else None,
        "date_iso": computed.isoformat() if computed else None,
    }


def resolve_ics_deadlines(section, corpus, answers):
    """Resolve an ``ics`` output section's ``deadline_ids`` to computed events.

    Returns one dict per referenced deadline, in the section's declared order:
    ``{id, label, description, date}`` where ``date`` is the ``compute_deadline``
    result — a ``date``, or ``None`` when the source answer isn't filled in yet.

    The single place an ics section's deadlines are resolved and computed,
    shared by the renderer's ``ics`` handler (which formats them for the page)
    and the ``.ics`` download view (which turns the computed ones into calendar
    events) — so the downloaded calendar can't drift from what the page shows.
    The loader guarantees every id resolves, so the lookup never misses.
    """
    by_id = {deadline.id: deadline for deadline in corpus.deadlines}
    resolved = []
    for deadline_id in section.deadline_ids:
        deadline = by_id[deadline_id]
        resolved.append(
            {
                "id": deadline.id,
                "label": deadline.label,
                "description": deadline.description,
                "date": compute_deadline(deadline, answers),
            }
        )
    return resolved
