"""The guided page's download files — pure, DB-free.

``ics_artifact`` and ``vcf_artifact`` turn resolved deadline and contact
dicts into a ``DownloadArtifact`` (content type, filename, body). The bodies
are parsed back with ``vobject`` to assert the dicts became real calendar
events and cards.
"""

from datetime import date

import vobject

from litigant_portal.app.topic_flow.downloads import (
    ics_artifact,
    vcf_artifact,
)

UID_PREFIX = "alpha-pets-standard-calendar"


def _resolved_deadline(id, label, date, description=""):
    return {"id": id, "label": label, "description": description, "date": date}


def _ics(*resolved):
    return ics_artifact(
        list(resolved), uid_prefix=UID_PREFIX, filename="calendar.ics"
    )


# --- ics_artifact -----------------------------------------------------------


def test_ics_sets_calendar_content_type_and_filename():
    artifact = _ics()
    assert artifact.content_type == "text/calendar; charset=utf-8"
    assert artifact.filename == "calendar.ics"


def test_ics_body_carries_each_dated_deadline_as_an_event():
    artifact = _ics(
        _resolved_deadline(
            "renewal", "License renewal", date(2027, 2, 1), "One year on."
        )
    )
    cal = vobject.readOne(artifact.body)
    assert cal.vevent.summary.value == "License renewal"
    assert cal.vevent.description.value == "One year on."
    assert cal.vevent.dtstart.value == date(2027, 2, 1)


def test_ics_prefixes_each_uid_and_skips_dateless_deadlines():
    artifact = _ics(
        _resolved_deadline("answer_due", "Answer due", date(2026, 3, 3)),
        _resolved_deadline("hearing", "Hearing", None),
    )
    events = vobject.readOne(artifact.body).contents.get("vevent", [])
    assert [e.uid.value for e in events] == [
        f"{UID_PREFIX}-answer_due@litigantportal.com"
    ]


def test_ics_without_a_dated_deadline_is_an_empty_but_valid_calendar():
    cal = vobject.readOne(_ics(_resolved_deadline("d", "D", None)).body)
    assert "vevent" not in cal.contents


def test_ics_uid_is_stable_across_downloads():
    # Same flow + block + deadline → same UID, so a re-download updates the
    # calendar event rather than duplicating it.
    resolved = _resolved_deadline("renewal", "Renewal", date(2027, 2, 1))
    assert (
        vobject.readOne(_ics(resolved).body).vevent.uid.value
        == vobject.readOne(_ics(resolved).body).vevent.uid.value
    )


# --- vcf_artifact -----------------------------------------------------------


def _resolved_contact(id, name, **fields):
    blank = dict.fromkeys(
        ("phone", "email", "url", "address", "hours", "note"), None
    )
    return {"id": id, "name": name, **blank, **fields}


def _vcf(*resolved):
    return vcf_artifact(
        list(resolved),
        uid_prefix="alpha-pets-standard-contacts",
        filename="contacts.vcf",
    )


def test_vcf_sets_vcard_content_type_and_filename():
    artifact = _vcf()
    assert artifact.content_type == "text/vcard; charset=utf-8"
    assert artifact.filename == "contacts.vcf"


def test_vcf_body_carries_each_contact_as_a_card_in_order():
    artifact = _vcf(
        _resolved_contact("clerk", "Clerk", phone="555-1234"),
        _resolved_contact("aid", "Legal Aid", email="help@aid.example"),
    )
    cards = list(vobject.readComponents(artifact.body))
    assert [card.fn.value for card in cards] == ["Clerk", "Legal Aid"]
    assert cards[0].tel.value == "555-1234"
    assert cards[1].email.value == "help@aid.example"


def test_vcf_prefixes_each_uid_with_the_given_prefix():
    artifact = _vcf(
        _resolved_contact("clerk", "Clerk"), _resolved_contact("aid", "Aid")
    )
    cards = list(vobject.readComponents(artifact.body))
    assert [card.uid.value for card in cards] == [
        "alpha-pets-standard-contacts-clerk@litigantportal.com",
        "alpha-pets-standard-contacts-aid@litigantportal.com",
    ]


def test_vcf_folds_hours_into_the_note_so_import_keeps_it():
    # vCard has no hours field; without folding, "call 9-4" is lost on import.
    artifact = _vcf(
        _resolved_contact("clerk", "Clerk", hours="9-4 M-F", note="Window 3")
    )
    note = vobject.readOne(artifact.body).note.value
    assert "Window 3" in note
    assert "Hours: 9-4 M-F" in note


def test_vcf_emits_no_note_without_hours_or_a_note():
    card = vobject.readOne(_vcf(_resolved_contact("clerk", "Clerk")).body)
    assert "note" not in card.contents
