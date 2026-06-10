"""Deadline math for Topic Flow.

A corpus ``Deadline`` is an ``offset_days`` from a gathered date — e.g. "30 days
after the notice was published". This module turns that relative definition plus
the user's answers into a concrete ``date``.

Pure and AI-free, mirroring ``renderer.py``: no session/request machinery, no
corpus re-validation (validity is guaranteed upstream at load). The one thing it
guards is *user* input — an absent or malformed date yields ``None`` (the
"fill the date first" state), never an exception.
"""

from datetime import date, timedelta


def compute_deadline(deadline, answers):
    """Return ``deadline``'s date from ``answers``, or ``None`` if uncomputable.

    Reads the answer to ``deadline.offset_from`` (a ``date`` question, so an ISO
    ``YYYY-MM-DD`` string) and adds ``offset_days``. Returns ``None`` when that
    answer is absent, blank, or unparseable — a half-filled form is normal, not
    an error.
    """
    raw = answers.get(deadline.offset_from)
    if not raw:
        return None
    try:
        gathered = date.fromisoformat(raw)
    except ValueError:
        return None
    return gathered + timedelta(days=deadline.offset_days)


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
