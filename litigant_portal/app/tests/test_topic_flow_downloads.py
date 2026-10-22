"""Download dispatch for Topic Flow output sections — pure, DB-free.

``find_downloadable`` resolves an output section by id and gates out the types
with no download handler (info / fact_gather / summary / packet → the view's
404). ``build_download`` turns a downloadable section + the user's answers into
a ``DownloadArtifact`` (content type, filename, bytes).

The ``.ics`` body is parsed back with ``vobject`` to assert the computed
deadline became a real calendar event — and, crucially, that it goes through
the same ``resolve_ics_deadlines`` the page renders with, so the download can't
drift from what's on screen.
"""

import re
from datetime import date

import vobject

from litigant_portal.app.topic_flow.downloads import (
    build_download,
    find_downloadable,
    ics_artifact,
    vcf_artifact,
)
from litigant_portal.app.topic_flow.schema import (
    Contact,
    Corpus,
    Deadline,
    FactGatherSection,
    IcsOutput,
    Metadata,
    Question,
    SummaryOutput,
    VcfOutput,
)

# An answered name_change_publication_date; 30 days on = 2026-03-03.
ANSWERS = {"name_change_publication_date": "2026-02-01"}


def _corpus():
    return Corpus(
        metadata=Metadata(
            court="test-court",
            topic="test_topic",
            role="petitioner",
            title="T",
        ),
        deadlines=[
            Deadline(
                id="publication_wait",
                label="30-day publication wait",
                offset_days=30,
                offset_from="name_change_publication_date",
                description="Judge may review after this.",
            )
        ],
        contacts=[
            Contact(
                id="clerk",
                name="Clerk of Court",
                phone="555-1234",
                hours="9-4 M-F",
                note="Window 3",
            )
        ],
        sections=[
            FactGatherSection(
                kind="fact_gather",
                id="key_dates",
                questions=[
                    Question(
                        id="name_change_publication_date",
                        label="When",
                        type="date",
                    )
                ],
            ),
            IcsOutput(
                kind="output",
                output_type="ics",
                id="deadlines_calendar",
                heading="Add deadlines to your calendar",
                deadline_ids=["publication_wait"],
            ),
            VcfOutput(
                kind="output",
                output_type="vcf",
                id="contacts_card",
                heading="Save these contacts",
                contact_ids=["clerk"],
            ),
            SummaryOutput(
                kind="output",
                output_type="summary",
                id="recap",
                heading="Summary",
            ),
        ],
    )


def _ics_section(corpus):
    return find_downloadable(corpus, "deadlines_calendar")


# --- find_downloadable ------------------------------------------------------


def test_resolves_the_ics_output_section():
    section = find_downloadable(_corpus(), "deadlines_calendar")
    assert section is not None
    assert section.output_type == "ics"


def test_none_for_an_output_with_no_download_handler():
    # summary is an output, but on-page only — not downloadable.
    assert find_downloadable(_corpus(), "recap") is None


def test_none_for_a_non_output_section():
    # fact_gather isn't an output at all — a stray /download/key_dates/ → 404.
    assert find_downloadable(_corpus(), "key_dates") is None


def test_none_for_an_unknown_id():
    assert find_downloadable(_corpus(), "nope") is None


# --- build_download (ics) ---------------------------------------------------


def test_sets_calendar_content_type_and_filename():
    corpus = _corpus()
    artifact = build_download(_ics_section(corpus), corpus, ANSWERS)
    assert artifact.content_type == "text/calendar; charset=utf-8"
    assert artifact.filename == "deadlines_calendar.ics"


def test_body_carries_the_computed_deadline_as_an_event():
    corpus = _corpus()
    artifact = build_download(_ics_section(corpus), corpus, ANSWERS)
    cal = vobject.readOne(artifact.body)
    assert cal.vevent.summary.value == "30-day publication wait"
    # The computed date (offset applied), not the raw gathered date.
    assert cal.vevent.dtstart.value == date(2026, 3, 3)


def test_omits_deadlines_without_a_computable_date():
    # No answer yet → the deadline isn't a calendar event (empty, valid cal).
    corpus = _corpus()
    artifact = build_download(_ics_section(corpus), corpus, {})
    cal = vobject.readOne(artifact.body)
    assert "vevent" not in cal.contents


def test_uid_is_stable_across_downloads():
    # Same flow + section + deadline → same UID, so a re-download updates the
    # calendar event rather than duplicating it.
    corpus = _corpus()
    first = build_download(_ics_section(corpus), corpus, ANSWERS)
    again = build_download(_ics_section(corpus), corpus, ANSWERS)
    assert (
        vobject.readOne(first.body).vevent.uid.value
        == vobject.readOne(again.body).vevent.uid.value
    )


def test_content_ics_output_is_unchanged():
    # The handler now goes through the shared ics_artifact; the bytes the
    # content path served before the split are pinned here, DTSTAMP aside.
    corpus = _corpus()
    artifact = build_download(_ics_section(corpus), corpus, ANSWERS)
    assert artifact.filename == "deadlines_calendar.ics"
    body = re.sub(r"DTSTAMP:\d{8}T\d{6}Z", "DTSTAMP:<now>", artifact.body)
    assert body == (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Free Law Project//Litigant Portal Topic Flow//EN\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:test-court-test_topic-petitioner-deadlines_calendar-"
        "publication_wait@li\r\n tigantportal.com\r\n"
        "DTSTART;VALUE=DATE:20260303\r\n"
        "DESCRIPTION:Judge may review after this.\r\n"
        "DTSTAMP:<now>\r\n"
        "SUMMARY:30-day publication wait\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )


# --- ics_artifact (shared by both paths) ------------------------------------


def test_ics_artifact_prefixes_each_uid_and_skips_dateless_deadlines():
    artifact = ics_artifact(
        [
            {
                "id": "answer_due",
                "label": "Answer due",
                "description": "",
                "date": date(2026, 3, 3),
            },
            {
                "id": "hearing",
                "label": "Hearing",
                "description": "",
                "date": None,
            },
        ],
        uid_prefix="alpha-pets-standard-calendar",
        filename="calendar.ics",
    )
    assert artifact.filename == "calendar.ics"
    assert artifact.content_type == "text/calendar; charset=utf-8"
    cal = vobject.readOne(artifact.body)
    events = cal.contents.get("vevent", [])
    assert [e.uid.value for e in events] == [
        "alpha-pets-standard-calendar-answer_due@litigantportal.com"
    ]
    assert events[0].dtstart.value == date(2026, 3, 3)


# --- build_download (vcf) ---------------------------------------------------
# A vcf section dispatches to the vCard builder, independent of answers (contacts
# are static corpus data). Body is parsed back with vobject to assert the contact
# became a real card via the same resolve_vcf_contacts the page renders with.


def _vcf_section(corpus):
    return find_downloadable(corpus, "contacts_card")


def test_resolves_the_vcf_output_section():
    section = find_downloadable(_corpus(), "contacts_card")
    assert section is not None
    assert section.output_type == "vcf"


def test_sets_vcard_content_type_and_filename():
    corpus = _corpus()
    artifact = build_download(_vcf_section(corpus), corpus, {})
    assert artifact.content_type == "text/vcard; charset=utf-8"
    assert artifact.filename == "contacts_card.vcf"


def test_vcf_body_carries_the_contact_as_a_card():
    corpus = _corpus()
    artifact = build_download(_vcf_section(corpus), corpus, {})
    card = vobject.readOne(artifact.body)
    assert card.fn.value == "Clerk of Court"
    assert card.tel.value == "555-1234"


def test_vcf_folds_hours_into_the_note_so_import_keeps_it():
    # vCard has no hours field; without folding, "call 9-4" is lost on import.
    corpus = _corpus()
    artifact = build_download(_vcf_section(corpus), corpus, {})
    note = vobject.readOne(artifact.body).note.value
    assert "Window 3" in note
    assert "Hours: 9-4 M-F" in note


def test_vcf_uid_is_stable_across_downloads():
    corpus = _corpus()
    first = build_download(_vcf_section(corpus), corpus, {})
    again = build_download(_vcf_section(corpus), corpus, {})
    assert (
        vobject.readOne(first.body).uid.value
        == vobject.readOne(again.body).uid.value
    )


def test_content_vcf_output_is_unchanged():
    # The handler now goes through the shared vcf_artifact; the bytes the
    # content path served before the split are pinned here.
    corpus = _corpus()
    artifact = build_download(_vcf_section(corpus), corpus, {})
    assert artifact.filename == "contacts_card.vcf"
    assert artifact.body == (
        "BEGIN:VCARD\r\n"
        "VERSION:3.0\r\n"
        "UID:test-court-test_topic-petitioner-contacts_card-clerk"
        "@litigantportal.com\r\n"
        "FN:Clerk of Court\r\n"
        "NOTE:Window 3\\nHours: 9-4 M-F\r\n"
        "ORG:Clerk of Court\r\n"
        "TEL:555-1234\r\n"
        "END:VCARD\r\n"
    )


# --- vcf_artifact (shared by both paths) ------------------------------------


def _resolved_contact(id, name, **fields):
    blank = dict.fromkeys(
        ("phone", "email", "url", "address", "hours", "note"), None
    )
    return {"id": id, "name": name, **blank, **fields}


def test_vcf_artifact_prefixes_each_uid_with_the_given_prefix():
    artifact = vcf_artifact(
        [
            _resolved_contact("clerk", "Clerk", phone="555-1234"),
            _resolved_contact("aid", "Legal Aid"),
        ],
        uid_prefix="alpha-pets-standard-contacts",
        filename="contacts.vcf",
    )
    assert artifact.filename == "contacts.vcf"
    assert artifact.content_type == "text/vcard; charset=utf-8"
    cards = list(vobject.readComponents(artifact.body))
    assert [card.uid.value for card in cards] == [
        "alpha-pets-standard-contacts-clerk@litigantportal.com",
        "alpha-pets-standard-contacts-aid@litigantportal.com",
    ]
    assert [card.fn.value for card in cards] == ["Clerk", "Legal Aid"]
