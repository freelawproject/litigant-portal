"""Deadline math for Topic Flow — pure, DB-free (runs in the fast suite).

``compute_deadline`` turns a corpus ``Deadline`` (an ``offset_days`` from a
gathered date) plus the answer dict into a concrete date. The date string is
whatever the ``<input type=date>`` submitted (ISO ``YYYY-MM-DD``). Validity of
the *corpus* is guaranteed upstream at load; the only thing that can go wrong
here is **missing or malformed user input**, which must yield ``None`` (the
"fill the date first" affordance) rather than raise — a half-filled form is the
normal state, not an error.
"""

from datetime import date

from litigant_portal.app.topic_flow.deadlines import compute_deadline
from litigant_portal.app.topic_flow.schema import Deadline


def _deadline(offset_days=30, offset_from="publication_date"):
    return Deadline(
        id="d1", label="L", offset_days=offset_days, offset_from=offset_from
    )


def test_adds_offset_days_to_the_gathered_date():
    # The core contract: gathered date + offset_days = the computed deadline.
    result = compute_deadline(
        _deadline(30), {"publication_date": "2026-01-01"}
    )
    assert result == date(2026, 1, 31)


def test_zero_offset_returns_the_gathered_date_itself():
    result = compute_deadline(_deadline(0), {"publication_date": "2026-01-01"})
    assert result == date(2026, 1, 1)


def test_negative_offset_returns_an_earlier_date():
    # offset_days can point backward (e.g. "respond N days *before* the hearing").
    result = compute_deadline(
        _deadline(-10), {"publication_date": "2026-01-01"}
    )
    assert result == date(2025, 12, 22)


def test_absent_answer_returns_none():
    # The source question hasn't been answered yet — not an error.
    assert compute_deadline(_deadline(), {}) is None


def test_empty_string_answer_returns_none():
    # A rendered-but-blank date field submits "" — still "no date yet".
    assert compute_deadline(_deadline(), {"publication_date": ""}) is None


def test_unparseable_date_returns_none_without_raising():
    # Defensive: never let a malformed value 500 the page.
    assert (
        compute_deadline(_deadline(), {"publication_date": "not-a-date"})
        is None
    )
