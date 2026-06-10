"""Generate downloadable file artifacts from Topic Flow corpus data.

Currently: an iCalendar (``.ics``) from a list of computed deadline events — a
pure projection with no corpus, no answers, no host page, mirroring the pure
style of ``deadlines.py``/``renderer.py``. The view layer resolves the corpus,
reads the session AnswerStore, and computes the dates; this module only turns
the resulting events into bytes, so the field mapping is unit-testable without
Django and ``vobject`` owns RFC 5545 escaping and line folding.

The future ``.vcf`` generator (a Contact → vCard, #473) lands here too — same
"data shape in, file bytes out" contract — which is why the module is named for
artifacts in general, not just calendars.
"""

from datetime import datetime

import vobject

# vobject's own UTC tzinfo (dateutil's ``tzutc``). DTSTAMP must be UTC, and
# vobject only serializes a tzinfo it can map to a TZID — Python's stdlib
# ``timezone.utc`` raises "Unable to guess TZID", so reuse vobject's singleton.
from vobject.icalendar import utc

# Identifies the product that produced the file (RFC 5545 PRODID). Overrides
# vobject's generic default so calendar apps attribute the import to us.
_PRODID = "-//Free Law Project//Litigant Portal Topic Flow//EN"


def deadlines_to_ics(events) -> str:
    """Serialize computed deadline ``events`` to an iCalendar string.

    Each event is a dict ``{uid, summary, description, date}`` — already
    resolved by the caller. ``date`` is a ``datetime.date`` (no clock time): a
    deadline is an all-day event, emitted as a ``VALUE=DATE`` ``DTSTART`` so no
    timezone is implied. ``description`` is optional — ``None``/empty emits no
    ``DESCRIPTION`` line. ``uid`` is supplied by the caller (stable per
    deadline) so re-downloading updates the event rather than duplicating it.

    An empty ``events`` list yields a valid, event-free calendar.
    """
    cal = vobject.iCalendar()
    cal.add("prodid").value = _PRODID
    # One shared stamp for the whole file: the moment it was generated.
    generated_at = datetime.now(utc)
    for event in events:
        vevent = cal.add("vevent")
        vevent.add("uid").value = event["uid"]
        vevent.add("dtstamp").value = generated_at
        vevent.add("summary").value = event["summary"]
        # A plain date (not datetime) makes vobject emit DTSTART;VALUE=DATE.
        vevent.add("dtstart").value = event["date"]
        if event.get("description"):
            vevent.add("description").value = event["description"]
    return cal.serialize()
