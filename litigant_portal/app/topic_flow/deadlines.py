"""
Display formatting for deadlines computed by the state projector.
"""

from litigant_portal.app.formatting import format_long_date


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
