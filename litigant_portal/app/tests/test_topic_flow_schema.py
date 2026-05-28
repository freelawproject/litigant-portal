"""Schema contract tests for Topic Flow corpora.

These lock the schema *decisions* (nested discriminated-union routing,
extra-key rejection, slug shape, required questions) — not Pydantic itself.
"""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from litigant_portal.app.topic_flow.schema import Corpus

FIXTURE = Path(__file__).resolve().parents[3] / "content" / "_test_fixture.yml"


def _fixture():
    return yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))


def test_fixture_routes_to_concrete_section_types():
    corpus = Corpus.model_validate(_fixture())
    assert [type(s).__name__ for s in corpus.sections] == [
        "InfoSection",
        "FactGatherSection",
        "IcsOutput",
        "VcfOutput",
        "PacketOutput",
        "SummaryOutput",
    ]


def test_unknown_section_kind_rejected():
    data = _fixture()
    data["sections"] = [{"kind": "bogus", "id": "x"}]
    with pytest.raises(ValidationError):
        Corpus.model_validate(data)


def test_unknown_output_type_rejected():
    data = _fixture()
    data["sections"] = [
        {"kind": "output", "output_type": "pdf", "id": "x", "heading": "h"}
    ]
    with pytest.raises(ValidationError):
        Corpus.model_validate(data)


def test_extra_key_rejected():
    data = _fixture()
    data["metadata"]["surprise"] = "nope"
    with pytest.raises(ValidationError):
        Corpus.model_validate(data)


def test_bad_slug_rejected():
    data = _fixture()
    data["metadata"]["court"] = "Bad Court"
    with pytest.raises(ValidationError):
        Corpus.model_validate(data)


def test_fact_gather_requires_a_question():
    data = _fixture()
    data["sections"] = [{"kind": "fact_gather", "id": "fg", "questions": []}]
    with pytest.raises(ValidationError):
        Corpus.model_validate(data)


def test_optional_lists_and_question_defaults():
    corpus = Corpus.model_validate(
        {
            "metadata": {
                "court": "c",
                "topic": "t",
                "role": "r",
                "title": "T",
            },
            "sections": [
                {
                    "kind": "fact_gather",
                    "id": "fg",
                    "questions": [{"id": "q", "label": "Q"}],
                }
            ],
        }
    )
    assert corpus.contacts == []
    assert corpus.deadlines == []
    question = corpus.sections[0].questions[0]
    assert question.type == "text"
    assert question.required is False
