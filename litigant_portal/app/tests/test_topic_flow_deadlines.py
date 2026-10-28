"""Deadline math for Topic Flow — pure, DB-free (runs in the fast suite).

``deadline_date`` turns an ``offset_days`` from a gathered date plus the
answer dict into a concrete date. The date string is whatever the
``<input type=date>`` submitted (ISO ``YYYY-MM-DD``). The only thing that can
go wrong here is **missing or malformed user input**, which must yield
``None`` (the "fill the date first" affordance) rather than raise — a
half-filled form is the normal state, not an error.
"""

from datetime import date

import pytest

from litigant_portal.app.topic_flow.deadlines import (
    deadline_date,
    deadline_display,
)

ANSWERS = {"license_date": "2026-02-01"}


@pytest.mark.parametrize(
    ("offset_days", "expected"),
    [
        (30, date(2026, 3, 3)),
        (0, date(2026, 2, 1)),
        (-10, date(2026, 1, 22)),
    ],
    ids=["forward", "zero", "backward"],
)
def test_deadline_date_adds_the_offset_to_the_stored_iso_date(
    offset_days, expected
):
    assert deadline_date(offset_days, "license_date", ANSWERS) == expected


@pytest.mark.parametrize(
    "answers",
    [
        {},
        {"license_date": ""},
        {"license_date": None},
        {"license_date": "March 3"},
        {"license_date": "01/02/2026"},
        {"license_date": ["2026-03-03"]},
    ],
    ids=["absent", "blank", "none", "prose", "non-iso", "not-a-string"],
)
def test_deadline_date_is_none_when_the_source_is_missing_or_unparseable(
    answers,
):
    # The chat may store any shape; the page must not 500 on it.
    assert deadline_date(30, "license_date", answers) is None


def test_deadline_display_formats_a_computed_date_and_leaves_none_blank():
    resolved = {
        "id": "d1",
        "label": "L",
        "description": "D",
        "date": date(2026, 3, 3),
    }
    assert deadline_display(resolved) == {
        "label": "L",
        "description": "D",
        "date_display": "Tuesday, March 3, 2026",
        "date_iso": "2026-03-03",
    }
    pending = deadline_display({**resolved, "date": None})
    assert pending["date_display"] is None and pending["date_iso"] is None


def test_deadline_display_single_digit_day_has_no_leading_zero():
    resolved = {"label": "L", "description": "", "date": date(2026, 3, 3)}
    assert (
        deadline_display(resolved)["date_display"] == "Tuesday, March 3, 2026"
    )
