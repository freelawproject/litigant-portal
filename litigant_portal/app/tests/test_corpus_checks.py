"""Tests for the corpus system check.

The check has two halves: the directory-structure walk and the schema
load. Both surface as ``corpus.E001``, so a broken corpus fails at boot
instead of serving wrong content. The structure tests point the check at
a throwaway corpus tree; the paths are module globals in two namespaces
(the selectors define them, the checks import them), so both get patched.
"""

import pytest

from litigant_portal.app.checks import corpus as checks
from litigant_portal.app.checks.corpus import (
    check_corpus,
    check_corpus_directory_structure,
)
from litigant_portal.app.selectors import corpus as selectors


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
