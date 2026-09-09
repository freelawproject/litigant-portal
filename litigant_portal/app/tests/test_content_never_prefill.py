"""Drift guard: the name/county questions real content asks never echo back.

The ND name-change flows collect them for the docassemble prefill, not to
display them, and a content-side addition that misses ``NEVER_PREFILL`` would
only surface on a shared terminal. DB-free.
"""

import pytest

from litigant_portal.app.topic_flow.loader import CorpusLoader
from litigant_portal.app.topic_flow.registry import CONTENT_DIR
from litigant_portal.app.topic_flow.renderer import NEVER_PREFILL

NAME_CHANGE_FLOWS = [
    "adult-name-change-standard.yml",
    "adult-name-change-waiver.yml",
]
IDENTITY_QUESTIONS = ["first_name", "middle_name", "last_name", "county"]


def _question_ids(file_name):
    path = CONTENT_DIR / file_name
    corpus = CorpusLoader.load(path)
    return [
        question.id
        for section in corpus.sections
        if section.kind == "fact_gather"
        for question in section.questions
    ]


@pytest.mark.parametrize("file_name", NAME_CHANGE_FLOWS)
@pytest.mark.parametrize("question_id", IDENTITY_QUESTIONS)
def test_name_change_flow_collects_the_identity_question(
    file_name, question_id
):
    assert question_id in _question_ids(file_name)


@pytest.mark.parametrize("question_id", IDENTITY_QUESTIONS)
def test_identity_question_is_never_prefilled(question_id):
    assert question_id in NEVER_PREFILL
