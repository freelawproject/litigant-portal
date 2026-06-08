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
