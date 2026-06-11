"""Generate downloadable file artifacts from Topic Flow corpus data.

Two generators, both pure projections — a list of already-resolved dicts in,
file bytes out, no corpus / answers / host page, mirroring the pure style of
``deadlines.py``/``renderer.py``:

- ``deadlines_to_ics`` — computed deadline events → an iCalendar (``.ics``).
- ``contacts_to_vcf`` — resolved contacts → vCards (``.vcf``).

The view layer resolves the corpus, reads the session AnswerStore, and computes
the data; this module only turns the resulting dicts into bytes, so the field
mapping is unit-testable without Django and ``vobject`` owns the RFC escaping
and line folding (RFC 5545 for iCalendar, RFC 6350 for vCard).
"""

from datetime import datetime

import vobject

# vobject's own UTC tzinfo (dateutil's ``tzutc``). DTSTAMP must be UTC, and
# vobject only serializes a tzinfo it can map to a TZID — Python's stdlib
# ``timezone.utc`` raises "Unable to guess TZID", so reuse vobject's singleton.
from vobject.icalendar import utc
from vobject.vcard import Address

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


def contacts_to_vcf(cards) -> str:
    """Serialize resolved ``cards`` to a vCard (``.vcf``) string.

    Each card is a dict ``{uid, name, phone, email, url, address, note}`` —
    already resolved by the caller. ``name`` sets both ``FN`` (the display name)
    and ``ORG``: our contacts are usually offices (clerk, legal aid), so a phone
    imports them as an organization card rather than mangling an office name
    into a person's given/family ``N``. Every other field is optional —
    ``None``/empty emits no line. ``uid`` is supplied by the caller (stable per
    contact) so re-downloading updates the card rather than duplicating it.

    Multiple cards concatenate into one file (a valid ``.vcf`` holds many
    vCards); an empty ``cards`` list yields an empty string.
    """
    out = []
    for card in cards:
        vcard = vobject.vCard()
        vcard.add("uid").value = card["uid"]
        vcard.add("fn").value = card["name"]
        # ORG is a structured (list) value; a single-element list is one org.
        vcard.add("org").value = [card["name"]]
        if card.get("phone"):
            vcard.add("tel").value = card["phone"]
        if card.get("email"):
            vcard.add("email").value = card["email"]
        if card.get("url"):
            vcard.add("url").value = card["url"]
        if card.get("address"):
            # A free-form one-line address rides in the ADR street component;
            # vobject escapes any commas/semicolons within it.
            vcard.add("adr").value = Address(street=card["address"])
        if card.get("note"):
            vcard.add("note").value = card["note"]
        out.append(vcard.serialize())
    return "".join(out)
