"""The guided page's download files.

Turns resolved deadline and contact dicts into a ``DownloadArtifact``
(content type, filename, body) for the download view. Generation lives in
``artifacts.py``; this module only maps the resolved dicts onto the file
fields and names the UIDs.
"""

from dataclasses import dataclass

from litigant_portal.app.topic_flow.artifacts import (
    contacts_to_vcf,
    deadlines_to_ics,
)


@dataclass(frozen=True)
class DownloadArtifact:
    filename: str
    content_type: str
    body: str


def ics_artifact(resolved, *, uid_prefix, filename):
    """Resolved deadline dicts → a ``.ics`` calendar.

    Only deadlines with a computable date become events — an unanswered date
    question yields no event (the "enter your dates first" state), so an
    all-pending list downloads an empty but valid calendar. The per-deadline
    ``UID`` is ``{uid_prefix}-{id}@litigantportal.com``, stable across
    re-downloads so a calendar app updates the event instead of duplicating
    it.
    """
    events = [
        {
            "uid": f"{uid_prefix}-{deadline['id']}@litigantportal.com",
            "summary": deadline["label"],
            "description": deadline["description"],
            "date": deadline["date"],
        }
        for deadline in resolved
        if deadline["date"] is not None
    ]
    return DownloadArtifact(
        filename=filename,
        # Declare UTF-8 explicitly: deadline labels/descriptions are author-
        # supplied and may carry non-ASCII. RFC 5545 defaults text/calendar to
        # UTF-8, but stating it beats relying on the client to honor the default.
        content_type="text/calendar; charset=utf-8",
        body=deadlines_to_ics(events),
    )


def _contact_note(resolved):
    """Combine a contact's free-text note and hours into the vCard NOTE.

    vCard has no native "hours" field, so opening hours would be lost on import
    — for our audience ("call the clerk between 9–4") that's the useful part.
    Fold it into NOTE under the existing note so it survives. Returns ``None``
    when neither is present (no NOTE line emitted).
    """
    parts = []
    if resolved["note"]:
        parts.append(resolved["note"])
    if resolved["hours"]:
        parts.append(f"Hours: {resolved['hours']}")
    return "\n".join(parts) or None


def vcf_artifact(resolved, *, uid_prefix, filename):
    """Resolved contact dicts → a ``.vcf`` vCard file.

    The per-contact ``UID`` is ``{uid_prefix}-{id}@litigantportal.com``,
    stable across re-downloads so a phone updates the saved contact instead
    of duplicating it.
    """
    cards = [
        {
            "uid": f"{uid_prefix}-{contact['id']}@litigantportal.com",
            "name": contact["name"],
            "phone": contact["phone"],
            "email": contact["email"],
            "url": contact["url"],
            "address": contact["address"],
            "note": _contact_note(contact),
        }
        for contact in resolved
    ]
    return DownloadArtifact(
        filename=filename,
        # Declare UTF-8 explicitly (see ics_artifact): contact names/notes are
        # author-supplied and may carry non-ASCII. RFC 6350 mandates UTF-8 for
        # vCard, so stating it keeps strict importers happy.
        content_type="text/vcard; charset=utf-8",
        body=contacts_to_vcf(cards),
    )
