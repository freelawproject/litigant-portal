"""Prefill payload tests: the row's handoff target and the rename. DB-free."""

from litigant_portal.app.models import TopicFlow
from litigant_portal.app.topic_flow.prefill import (
    flow_interview_target,
    prefill_variables,
)

MAPPING = {"first_name": "current_first", "county": "residence_county"}
REFERENCE = "docassemble.test:data/questions/petition.yml"


def test_flow_target_carries_the_reference_and_the_mapping():
    flow = TopicFlow(interview_reference=REFERENCE, interview_prefill=MAPPING)
    assert flow_interview_target(flow) == (REFERENCE, MAPPING)


def test_flow_target_is_none_without_a_reference():
    assert flow_interview_target(TopicFlow()) is None
    assert (
        flow_interview_target(
            TopicFlow(interview_reference="", interview_prefill=MAPPING)
        )
        is None
    )


def test_flow_with_an_empty_mapping_yields_an_empty_mapping():
    flow = TopicFlow(interview_reference=REFERENCE, interview_prefill={})
    assert flow_interview_target(flow) == (REFERENCE, {})


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
