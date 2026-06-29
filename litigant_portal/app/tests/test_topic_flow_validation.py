"""Unit tests for fact_gather answer validation (#525).

``validate_answers`` is pure and DB-free: given a corpus and a submitted
``{qid: value}`` map, it returns ``{qid: [error]}`` for empty ``required``
fields and ``choice`` answers outside the declared list. An empty dict means
the submission is valid. These run in the fast suite.
"""

from litigant_portal.app.topic_flow.schema import (
    Corpus,
    FactGatherSection,
    Metadata,
    Question,
)
from litigant_portal.app.topic_flow.validation import validate_answers


def _corpus():
    return Corpus(
        metadata=Metadata(court="c", topic="t", role="petitioner", title="T"),
        sections=[
            FactGatherSection(
                kind="fact_gather",
                id="facts",
                questions=[
                    Question(
                        id="pub_date",
                        label="Publication date",
                        type="date",
                        required=True,
                    ),
                    Question(
                        id="county",
                        label="County",
                        type="choice",
                        choices=["Cass", "Burleigh"],
                    ),
                    Question(id="note", label="Note", type="text"),
                ],
            )
        ],
    )


def test_empty_required_field_is_flagged():
    assert "pub_date" in validate_answers(_corpus(), {"pub_date": ""})


def test_whitespace_only_required_field_is_flagged():
    # A space-bar answer is no answer — must not satisfy `required`.
    assert "pub_date" in validate_answers(_corpus(), {"pub_date": "   "})


def test_filled_required_field_passes():
    assert validate_answers(_corpus(), {"pub_date": "2026-02-01"}) == {}


def test_choice_outside_declared_list_is_flagged():
    assert "county" in validate_answers(_corpus(), {"county": "Stark"})


def test_choice_within_declared_list_passes():
    assert validate_answers(_corpus(), {"county": "Cass"}) == {}


def test_empty_optional_choice_passes():
    # Not required + left blank → fine; the litigant may skip it.
    assert validate_answers(_corpus(), {"county": ""}) == {}


def test_absent_question_is_not_validated():
    # A required field missing from the submission belongs to a section that
    # wasn't posted — skipped, so no upfront error on an unreached section.
    assert validate_answers(_corpus(), {"note": "hi"}) == {}


def test_each_invalid_answer_is_keyed_by_its_question_id():
    errors = validate_answers(
        _corpus(), {"pub_date": "", "county": "Stark", "note": "fine"}
    )
    assert set(errors) == {"pub_date", "county"}
