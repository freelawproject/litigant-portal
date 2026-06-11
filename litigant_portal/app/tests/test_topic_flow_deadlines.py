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
from types import SimpleNamespace

from litigant_portal.app.topic_flow.deadlines import (
    compute_deadline,
    resolve_ics_deadlines,
)
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


# --- resolve_ics_deadlines --------------------------------------------------
# The shared resolver an ics section's renderer AND its .ics download view both
# call, so the page and the downloaded calendar compute from one source. It
# duck-types on ``section.deadline_ids`` and ``corpus.deadlines``; the stand-ins
# below carry just those attributes (real Deadline objects drive the math).


def _named_deadline(id, label, offset_days=30, description=None):
    return Deadline(
        id=id,
        label=label,
        offset_days=offset_days,
        offset_from="publication_date",
        description=description,
    )


def _section(*deadline_ids):
    return SimpleNamespace(deadline_ids=list(deadline_ids))


def _corpus(*deadlines):
    return SimpleNamespace(deadlines=list(deadlines))


def test_resolve_computes_each_referenced_deadlines_date():
    deadline = _named_deadline("pub_wait", "Publication wait", 30)
    (resolved,) = resolve_ics_deadlines(
        _section("pub_wait"),
        _corpus(deadline),
        {"publication_date": "2026-02-01"},
    )
    assert resolved["id"] == "pub_wait"
    assert resolved["label"] == "Publication wait"
    # 30 days after 2026-02-01 = 2026-03-03 — the raw date the .ics consumes.
    assert resolved["date"] == date(2026, 3, 3)


def test_resolve_date_is_none_when_answer_missing():
    # The view filters on this: a None-date deadline isn't a calendar event yet.
    (resolved,) = resolve_ics_deadlines(
        _section("pub_wait"), _corpus(_named_deadline("pub_wait", "Wait")), {}
    )
    assert resolved["date"] is None


def test_resolve_follows_section_order_not_corpus_order():
    # Order tracks the section's deadline_ids, not corpus.deadlines order —
    # the iteration source is the contract, so guard the wrong-collection bug.
    first = _named_deadline("a", "A", 5)
    second = _named_deadline("b", "B", 10)
    resolved = resolve_ics_deadlines(
        _section("b", "a"), _corpus(first, second), {}
    )
    assert [r["id"] for r in resolved] == ["b", "a"]


def test_resolve_carries_description():
    deadline = _named_deadline(
        "pub_wait", "Wait", description="Judge reviews."
    )
    (resolved,) = resolve_ics_deadlines(
        _section("pub_wait"), _corpus(deadline), {}
    )
    assert resolved["description"] == "Judge reviews."
