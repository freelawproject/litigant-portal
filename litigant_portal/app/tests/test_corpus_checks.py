"""Tests for the corpus system checks.

``check_corpus`` has two halves: the directory-structure walk and the
schema load. Both surface as ``corpus.E001``, so a broken corpus fails at
boot instead of serving wrong content. The structure tests point the check
at a throwaway corpus tree; the paths are module globals in two namespaces
(the selectors define them, the checks import them), so both get patched.
``corpus.W001`` warns when a flow decides a deadline, a packet form or a
gated question from a variable no marked page asks.
"""

from types import SimpleNamespace

import pytest

from litigant_portal.app.checks import corpus as checks
from litigant_portal.app.checks.corpus import (
    check_corpus,
    check_corpus_asks_decision_variables,
    check_corpus_directory_structure,
)
from litigant_portal.app.selectors import corpus as selectors
from litigant_portal.app.selectors.corpus import FlowSchema, VariableSchema


@pytest.fixture
def corpus_dir(tmp_path, monkeypatch):
    """A minimal valid corpus tree, patched into both namespaces."""
    (tmp_path / "variables.yml").write_text(
        "variables:\n  - name: full_name\n    label: Full name\n"
    )
    for module in (checks, selectors):
        monkeypatch.setattr(module, "CORPUS_DIR", tmp_path)
        monkeypatch.setattr(module, "FORMS_DIR", tmp_path / "forms")
        monkeypatch.setattr(module, "COURTS_DIR", tmp_path / "courts")
        monkeypatch.setattr(
            module, "VARIABLES_PATH", tmp_path / "variables.yml"
        )
    return tmp_path


def test_shipped_corpus_passes_the_check():
    assert check_corpus(None) == []


def test_minimal_corpus_passes(corpus_dir):
    assert check_corpus(None) == []


# Directory-structure rules


def test_missing_variables_yml(corpus_dir):
    (corpus_dir / "variables.yml").unlink()
    with pytest.raises(ValueError, match="variables.yml is missing"):
        check_corpus_directory_structure()


def test_unrecognized_file(corpus_dir):
    (corpus_dir / "forms").mkdir()
    (corpus_dir / "forms" / "notes.txt").write_text("scratch")
    with pytest.raises(ValueError, match="unrecognized file"):
        check_corpus_directory_structure()


def _branding_dir(corpus_dir):
    court = corpus_dir / "courts" / "alpha"
    (court / "branding").mkdir(parents=True)
    (court / "court.yml").write_text("name: Alpha\ncourt_name: Alpha Court")
    return court / "branding"


@pytest.mark.parametrize("name", ["logo.svg", "logo.png"])
def test_a_court_branding_image_is_recognized(corpus_dir, name):
    (_branding_dir(corpus_dir) / name).write_text("art")
    check_corpus_directory_structure()


def test_another_file_in_branding_is_unrecognized(corpus_dir):
    (_branding_dir(corpus_dir) / "logo.gif").write_text("art")
    with pytest.raises(ValueError, match="unrecognized file"):
        check_corpus_directory_structure()


def test_non_slug_name(corpus_dir):
    (corpus_dir / "forms").mkdir()
    (corpus_dir / "forms" / "Bad_Name.yml").write_text("name: Bad\nfields: []")
    with pytest.raises(ValueError, match="not a valid slug"):
        check_corpus_directory_structure()


def test_court_directory_without_court_yml(corpus_dir):
    (corpus_dir / "courts" / "north-dakota").mkdir(parents=True)
    with pytest.raises(ValueError, match="court.yml is missing"):
        check_corpus_directory_structure()


def test_topic_directory_without_topic_yml(corpus_dir):
    topic_dir = corpus_dir / "courts" / "north-dakota" / "topics" / "pets"
    topic_dir.mkdir(parents=True)
    (corpus_dir / "courts" / "north-dakota" / "court.yml").write_text(
        "name: North Dakota\ncourt_name: District Court\n"
    )
    with pytest.raises(ValueError, match="topic.yml is missing"):
        check_corpus_directory_structure()


# Both halves surface as corpus.E001


def test_broken_structure_returns_e001(corpus_dir):
    (corpus_dir / "variables.yml").unlink()
    (errors,) = check_corpus(None)
    assert errors.id == "corpus.E001"


def test_invalid_corpus_returns_e001(corpus_dir):
    (corpus_dir / "variables.yml").write_text(
        "variables:\n"
        "  - name: full_name\n"
        "    label: Full name\n"
        "  - name: full_name\n"
        "    label: Duplicate\n"
    )
    (errors,) = check_corpus(None)
    assert errors.id == "corpus.E001"
    assert "duplicate variable names" in errors.msg


# corpus.W001: a decision variable asked on no marked page


# adopted_on sets the deadline; adoption_shelter is asked only once adopted.
_GLOSSARY = {
    "adopted_on": VariableSchema(name="adopted_on", label="Adopted on"),
    "adopted": VariableSchema(name="adopted", label="Adopted"),
    "adoption_shelter": VariableSchema(
        name="adoption_shelter",
        label="Shelter",
        asked_when={"variable": "adopted", "value": True},
    ),
}


def _flow(*pages):
    """A flow with one page per ``(variables, on_page)`` and a deadline
    counted from ``adopted_on``."""
    return FlowSchema.model_validate(
        {
            "name": "Pets",
            "sections": [{"id": "start", "heading": "Start", "content": "C"}],
            "interview": [
                {"title": "Page", "variables": variables, "on_page": on_page}
                for variables, on_page in pages
            ],
            "deadlines": [
                {
                    "id": "due",
                    "label": "Due",
                    "offset_days": 30,
                    "offset_from": "adopted_on",
                }
            ],
        }
    )


def _corpus(monkeypatch, flow):
    corpus = SimpleNamespace(
        flows={("alpha", "pets", "standard"): flow}, variables=_GLOSSARY
    )
    monkeypatch.setattr(checks, "corpus_load", lambda: corpus)


def test_shipped_corpus_asks_every_decision_variable():
    assert check_corpus_asks_decision_variables(None) == []


def test_an_unmarked_deadline_source_warns_naming_the_flow_and_variable(
    monkeypatch,
):
    _corpus(monkeypatch, _flow((["adopted_on"], False)))
    (warning,) = check_corpus_asks_decision_variables(None)
    assert warning.id == "corpus.W001"
    assert "alpha/pets/standard" in warning.msg
    assert "adopted_on" in warning.msg


def test_a_marked_deadline_source_does_not_warn(monkeypatch):
    _corpus(monkeypatch, _flow((["adopted_on"], True)))
    assert check_corpus_asks_decision_variables(None) == []


def test_an_unmarked_gate_of_a_marked_question_warns(monkeypatch):
    _corpus(
        monkeypatch,
        _flow(
            (["adopted_on", "adopted"], False), (["adoption_shelter"], True)
        ),
    )
    (warning,) = check_corpus_asks_decision_variables(None)
    assert "adopted, adopted_on" in warning.msg


def test_a_corpus_that_fails_to_load_leaves_the_warning_to_e001(monkeypatch):
    def broken():
        raise ValueError("bad corpus")

    monkeypatch.setattr(checks, "corpus_load", broken)
    assert check_corpus_asks_decision_variables(None) == []
