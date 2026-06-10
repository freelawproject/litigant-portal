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

from datetime import date

import vobject

from litigant_portal.app.topic_flow.downloads import (
    build_download,
    find_downloadable,
)
from litigant_portal.app.topic_flow.schema import (
    Corpus,
    Deadline,
    FactGatherSection,
    IcsOutput,
    Metadata,
    Question,
    SummaryOutput,
)

# An answered publication_date; 30 days on = 2026-03-03.
ANSWERS = {"publication_date": "2026-02-01"}


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
                offset_from="publication_date",
                description="Judge may review after this.",
            )
        ],
        sections=[
            FactGatherSection(
                kind="fact_gather",
                id="key_dates",
                questions=[
                    Question(id="publication_date", label="When", type="date")
                ],
            ),
            IcsOutput(
                kind="output",
                output_type="ics",
                id="deadlines_calendar",
                heading="Add deadlines to your calendar",
                deadline_ids=["publication_wait"],
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
    assert artifact.content_type == "text/calendar"
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
