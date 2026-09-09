"""Display formatting shared across layers.

Deliberately Django-free so the topic-flow renderer can use it (that module
stays importable without Django configured), and deliberately not owned by
either caller: the flow page and the briefcase must show a litigant the same
date in the same shape, and a helper anchored to one of them drifts the moment
the other formats its own.
"""

import datetime


def format_long_date(value: datetime.date) -> str:
    """Human-readable date, e.g. "Tuesday, March 3, 2026".

    The day is interpolated as ``value.day`` rather than via strftime's
    ``%-d``. ``%-d`` (no-leading-zero day) is a glibc/BSD extension, not
    standard C, so it raises ``ValueError`` on platforms whose C library lacks
    it — notably Windows — which would crash rendering for a partner
    self-hosting LP there (#526). Weekday and month stay on strftime:
    ``%A``/``%B`` are standard and portable.
    """
    return f"{value.strftime('%A, %B')} {value.day}, {value.year}"
