"""File-artifact generators for Topic Flow — pure, DB-free (fast suite).

``deadlines_to_ics`` turns a list of already-computed deadline events into an
iCalendar (``.ics``) string. It is a pure projection — no corpus, no answers,
no Django — so it tests standalone like ``deadlines.py``; the download view
does the resolving/computing and hands this function plain events.

Tests round-trip through ``vobject`` (parse the output back) rather than
asserting raw lines, so they pin the *semantic* contract — summary, all-day
date, optional description, escaping survive a serialize→parse cycle — without
being brittle to vobject's exact line formatting, param order, or folding.
"""

from datetime import date, datetime

import vobject

from litigant_portal.app.topic_flow.artifacts import deadlines_to_ics


def _event(
    uid="publication_wait@litigantportal",
    summary="30-day publication wait",
    description=None,
    on=date(2026, 3, 3),
):
    return {
        "uid": uid,
        "summary": summary,
        "description": description,
        "date": on,
    }


def test_wraps_events_in_a_parseable_vcalendar():
    cal = vobject.readOne(deadlines_to_ics([_event()]))
    assert cal.name == "VCALENDAR"
    # VERSION is mandatory (RFC 5545); a calendar without it won't import.
    assert cal.version.value == "2.0"


def test_event_round_trips_summary_uid_and_date():
    cal = vobject.readOne(deadlines_to_ics([_event(on=date(2026, 3, 3))]))
    assert cal.vevent.summary.value == "30-day publication wait"
    assert cal.vevent.uid.value == "publication_wait@litigantportal"
    assert cal.vevent.dtstart.value == date(2026, 3, 3)


def test_deadline_is_an_all_day_event_not_a_timed_one():
    # All-day = a DATE value, not a DATE-TIME. A deadline has no clock time, and
    # a timed event would drag in timezone ambiguity. ``date`` (not ``datetime``)
    # is how that contract is expressed and parsed back.
    cal = vobject.readOne(deadlines_to_ics([_event(on=date(2026, 3, 3))]))
    value = cal.vevent.dtstart.value
    assert isinstance(value, date)
    assert not isinstance(value, datetime)


def test_each_event_becomes_its_own_vevent():
    out = deadlines_to_ics([_event(uid="a"), _event(uid="b"), _event(uid="c")])
    cal = vobject.readOne(out)
    assert {v.uid.value for v in cal.vevent_list} == {"a", "b", "c"}


def test_description_present_when_given():
    cal = vobject.readOne(
        deadlines_to_ics([_event(description="Judge may review after this.")])
    )
    assert cal.vevent.description.value == "Judge may review after this."


def test_description_omitted_when_none():
    # Absent field → no line, never an empty DESCRIPTION:.
    cal = vobject.readOne(deadlines_to_ics([_event(description=None)]))
    assert "description" not in cal.vevent.contents


def test_special_characters_survive_a_round_trip():
    # RFC 5545 reserves comma / semicolon / backslash in TEXT values; if the
    # generator didn't escape them, the parse back would split or corrupt the
    # value. Round-tripping intact proves escaping is correct.
    tricky = "Hearing, bring ID; see note\\ here"
    cal = vobject.readOne(deadlines_to_ics([_event(summary=tricky)]))
    assert cal.vevent.summary.value == tricky


def test_empty_event_list_is_still_a_valid_calendar():
    cal = vobject.readOne(deadlines_to_ics([]))
    assert cal.name == "VCALENDAR"
    assert "vevent" not in cal.contents
