"""Drift guard: content fact_gather ids are glossary variable names.

Answers from the content tree persist as VariableAnswer rows against
``corpus/variables.yml``, so ids and types must agree. The ``_``-prefixed
fixture is exempt. DB-free: both sides load from YAML.
"""

import pytest

from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.selectors.corpus import corpus_load_variables
from litigant_portal.app.topic_flow.loader import CorpusLoader
from litigant_portal.app.topic_flow.registry import (
    CONTENT_DIR,
    iter_corpus_paths,
)

# Content question ``type`` → the glossary data_type it may bind to.
_COMPATIBLE = {
    "text": VariableDataType.TEXT,
    "date": VariableDataType.DATE,
    "choice": VariableDataType.CHOICE,
}


def _questions():
    """(file name, question) for every fact_gather question in real content."""
    for path in iter_corpus_paths(CONTENT_DIR):
        corpus = CorpusLoader.load(path)
        for section in corpus.sections:
            if section.kind == "fact_gather":
                for question in section.questions:
                    yield path.name, question


@pytest.fixture(scope="module")
def glossary():
    return corpus_load_variables()


@pytest.mark.parametrize(
    ("file_name", "question"), _questions(), ids=lambda v: getattr(v, "id", v)
)
def test_question_id_is_a_glossary_variable(file_name, question, glossary):
    assert question.id in glossary, (
        f"{file_name} question '{question.id}' is not a glossary variable"
    )


@pytest.mark.parametrize(
    ("file_name", "question"), _questions(), ids=lambda v: getattr(v, "id", v)
)
def test_question_type_matches_glossary_data_type(
    file_name, question, glossary
):
    variable = glossary.get(question.id)
    if variable is None:
        pytest.skip("covered by test_question_id_is_a_glossary_variable")
    assert variable.data_type == _COMPATIBLE[question.type], (
        f"{file_name} '{question.id}' is {question.type}, "
        f"glossary says {variable.data_type}"
    )
    if question.type == "choice":
        allowed = {choice.value for choice in variable.choices}
        assert set(question.choices) <= allowed, (
            f"{file_name} '{question.id}' offers options the glossary "
            f"rejects: {set(question.choices) - allowed}"
        )
