"""Schema contract tests for Topic Flow corpora.

These lock the schema *decisions* (nested discriminated-union routing,
extra-key rejection, slug shape, required questions) — not Pydantic itself.
"""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from litigant_portal.app.topic_flow.schema import (
    Corpus,
    PacketForm,
    PacketOutput,
    Resource,
)

FIXTURE = Path(__file__).resolve().parents[2] / "content" / "_test_fixture.yml"


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
        "ResourcesOutput",
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


def test_packet_interview_url_optional_and_accepted():
    """interview_url defaults to None — the link-out is graceful when an author
    omits it, so existing packet corpora are unaffected — and is carried through
    when provided (the #543 docassemble handoff seam)."""
    base = {
        "kind": "output",
        "output_type": "packet",
        "id": "p",
        "heading": "Your packet",
        "forms": ["Petition for Name Change"],
    }
    assert PacketOutput.model_validate(base).interview_url is None
    url = "https://da.example/interview?i=docassemble.playground"
    assert (
        PacketOutput.model_validate(
            {**base, "interview_url": url}
        ).interview_url
        == url
    )


def test_packet_form_bare_string_coerces_to_unlinked_form():
    # Authoring shorthand: a plain string is the form name with no link, so
    # existing string-only corpora keep validating unchanged.
    packet = PacketOutput.model_validate(
        {
            "kind": "output",
            "output_type": "packet",
            "id": "p",
            "heading": "Your packet",
            "forms": ["Petition for Name Change"],
        }
    )
    assert packet.forms == [
        PacketForm(name="Petition for Name Change", url=None)
    ]


def test_packet_form_object_carries_its_url():
    pdf = "https://www.ndcourts.gov/.../Petition-Name-Change-Adult.pdf"
    packet = PacketOutput.model_validate(
        {
            "kind": "output",
            "output_type": "packet",
            "id": "p",
            "heading": "Your packet",
            "forms": [{"name": "Petition for Name Change", "url": pdf}],
        }
    )
    assert packet.forms[0].url == pdf


def test_packet_forms_may_mix_linked_and_unlinked():
    packet = PacketOutput.model_validate(
        {
            "kind": "output",
            "output_type": "packet",
            "id": "p",
            "heading": "Your packet",
            "forms": [
                "Notice",
                {"name": "Petition", "url": "https://ex/p.pdf"},
            ],
        }
    )
    assert packet.forms[0].url is None
    assert packet.forms[1].url == "https://ex/p.pdf"


def test_packet_form_rejects_unknown_key():
    # extra="forbid" — a typo'd form key fails loud instead of silently dropping.
    with pytest.raises(ValidationError):
        PacketOutput.model_validate(
            {
                "kind": "output",
                "output_type": "packet",
                "id": "p",
                "heading": "Your packet",
                "forms": [{"name": "Petition", "ulr": "https://typo"}],
            }
        )


def test_resource_requires_a_url():
    # A resource *is* a link — unlike Contact.url, the url is mandatory, so a
    # resource that would render as an unclickable label fails loud.
    with pytest.raises(ValidationError):
        Resource(id="r", label="Self-help page")


def test_resource_carries_label_url_and_optional_note():
    bare = Resource(id="r", label="Self-help", url="https://ex/help")
    assert bare.note is None
    noted = Resource(
        id="r", label="Self-help", url="https://ex/help", note="Official page."
    )
    assert noted.note == "Official page."


def test_resource_rejects_unknown_key():
    # extra="forbid" — a typo'd key fails loud instead of silently dropping.
    with pytest.raises(ValidationError):
        Resource.model_validate(
            {"id": "r", "label": "L", "url": "https://ex", "lable": "typo"}
        )


def test_resources_output_requires_at_least_one_reference():
    # min_length=1 — an empty resources section is an authoring mistake, not a
    # silently-empty list.
    data = _fixture()
    data["sections"] = [
        {
            "kind": "output",
            "output_type": "resources",
            "id": "official",
            "heading": "Official resources",
            "resource_ids": [],
        }
    ]
    with pytest.raises(ValidationError):
        Corpus.model_validate(data)
