"""Prefill payload tests: corpus mapping resolution and the rename. DB-free."""

from litigant_portal.app.topic_flow.prefill import (
    interview_target,
    prefill_variables,
)
from litigant_portal.app.topic_flow.schema import (
    Corpus,
    FactGatherSection,
    InfoSection,
    Metadata,
    PacketOutput,
    Question,
)

MAPPING = {"first_name": "current_first", "county": "residence_county"}
URL = "https://da.example.gov/interview/interview?i=petition.yml"


def _corpus(*sections):
    return Corpus(
        metadata=Metadata(court="c", topic="t", role="r", title="T"),
        sections=list(sections) or [_packet()],
    )


def _packet(*, interview_url=URL, mapping=None, id="filing_packet"):
    return PacketOutput(
        kind="output",
        output_type="packet",
        id=id,
        heading="Your filing packet",
        forms=["Petition"],
        interview_url=interview_url,
        interview_prefill=MAPPING if mapping is None else mapping,
    )


def test_target_carries_the_launch_url_and_its_mapping():
    assert interview_target(_corpus()) == (URL, MAPPING)


def test_target_is_none_without_a_packet_section():
    corpus = _corpus(
        InfoSection(kind="info", id="overview", heading="H", body="B")
    )
    assert interview_target(corpus) is None


def test_target_is_none_when_the_packet_has_no_interview():
    assert interview_target(_corpus(_packet(interview_url=None))) is None


def test_target_skips_a_packet_without_an_interview():
    corpus = _corpus(_packet(interview_url=None, id="forms_only"), _packet())
    assert interview_target(corpus) == (URL, MAPPING)


def test_unmapped_packet_yields_an_empty_mapping():
    assert interview_target(_corpus(_packet(mapping={}))) == (URL, {})


def test_variables_are_renamed_to_their_interview_names():
    answers = {"first_name": "Sandra", "county": "Burleigh"}
    assert prefill_variables(mapping=MAPPING, answers=answers) == {
        "current_first": "Sandra",
        "residence_county": "Burleigh",
    }


def test_an_unanswered_question_is_absent_from_the_payload():
    payload = prefill_variables(
        mapping=MAPPING, answers={"first_name": "Sandra"}
    )
    assert payload == {"current_first": "Sandra"}


def test_an_unmapped_answer_is_not_sent():
    payload = prefill_variables(
        mapping=MAPPING, answers={"phone_number": "555-0100"}
    )
    assert payload == {}


def test_an_empty_mapping_sends_nothing():
    assert prefill_variables(mapping={}, answers={"first_name": "S"}) == {}


def test_no_answers_at_all_sends_nothing():
    assert prefill_variables(mapping=MAPPING, answers={}) == {}


def test_a_date_stays_an_iso_string():
    mapping = {"name_change_publication_date": "publication_date"}
    answers = {"name_change_publication_date": "2026-05-01"}
    assert prefill_variables(mapping=mapping, answers=answers) == {
        "publication_date": "2026-05-01"
    }


def test_a_question_the_page_never_shows_still_reaches_the_payload():
    # NEVER_PREFILL governs rendering, not sending.
    corpus = _corpus(
        FactGatherSection(
            kind="fact_gather",
            id="your_information",
            questions=[Question(id="first_name", label="First name")],
        ),
        _packet(),
    )
    _, mapping = interview_target(corpus)
    assert prefill_variables(
        mapping=mapping, answers={"first_name": "Sandra"}
    ) == {"current_first": "Sandra"}
