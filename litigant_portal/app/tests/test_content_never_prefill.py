"""Drift guard: the ND name-change flows keep collecting the identity
questions the docassemble prefill maps (#531). DB-free.

The NEVER_PREFILL half of this guard was removed with the #638/#803 masking
(2026-09-23): saved answers now render back into the form.
"""

import pytest

from litigant_portal.app.topic_flow.loader import CorpusLoader
from litigant_portal.app.topic_flow.registry import CONTENT_DIR

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
