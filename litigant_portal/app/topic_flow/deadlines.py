"""Deadline math for Topic Flow.

A flow's deadline is an ``offset_days`` from a gathered date — e.g. "30 days
after the notice was published". This module turns that relative definition
plus the user's answers into a concrete ``date``.

Pure and AI-free: no session/request machinery, no corpus re-validation
(validity is guaranteed upstream at load). The one thing it guards is *user*
input — an absent or malformed date yields ``None`` (the "fill the date
first" state), never an exception. ``rows.py`` keys a deadline by its
``offset_from`` variable's name.
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
