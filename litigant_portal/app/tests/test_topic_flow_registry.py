"""Registry discovery/indexing tests + the Django system check."""

from pathlib import Path

from litigant_portal.app.topic_flow import checks
from litigant_portal.app.topic_flow.registry import CorpusRegistry

FIXTURE = Path(__file__).resolve().parents[2] / "content" / "_test_fixture.yml"
VALID = FIXTURE.read_text(encoding="utf-8")
# Schema-invalid: empty sections list.
BAD = "metadata: {court: c, topic: t, role: r, title: T}\nsections: []\n"
FIXTURE_KEY = ("test-court", "test_topic", "petitioner")


def test_registry_indexes_by_court_topic_role(tmp_path):
    (tmp_path / "real.yml").write_text(VALID)
    registry = CorpusRegistry(content_dir=tmp_path)
    assert registry.keys() == [FIXTURE_KEY]
    assert registry.get(*FIXTURE_KEY) is not None


def test_registry_skips_underscore_files(tmp_path):
    (tmp_path / "_draft.yml").write_text(VALID)
    registry = CorpusRegistry(content_dir=tmp_path)
    assert registry.keys() == []


def test_registry_skips_invalid_corpus_gracefully(tmp_path):
    (tmp_path / "good.yml").write_text(VALID)
    (tmp_path / "bad.yml").write_text(BAD)
    registry = CorpusRegistry(content_dir=tmp_path)
    # Bad file is logged and skipped; the good one still indexes; no raise.
    assert registry.keys() == [FIXTURE_KEY]


def test_registry_get_miss_returns_none(tmp_path):
    (tmp_path / "real.yml").write_text(VALID)
    registry = CorpusRegistry(content_dir=tmp_path)
    assert registry.get("no", "such", "corpus") is None


def test_check_passes_for_valid_corpus(tmp_path, monkeypatch):
    good = tmp_path / "good.yml"
    good.write_text(VALID)
    monkeypatch.setattr(checks, "iter_corpus_paths", lambda _dir: [good])
    assert checks.check_corpora(None) == []


def test_check_reports_invalid_corpus(tmp_path, monkeypatch):
    bad = tmp_path / "bad.yml"
    bad.write_text(BAD)
    monkeypatch.setattr(checks, "iter_corpus_paths", lambda _dir: [bad])
    errors = checks.check_corpora(None)
    assert len(errors) == 1
    assert errors[0].id == "topic_flow.E001"


def test_check_reports_duplicate_corpus_keys(tmp_path, monkeypatch):
    # Two files declaring the same (court, topic, role) — the later one
    # silently overwrites the earlier in the registry, so the check must
    # fail loud and name both colliding files.
    first = tmp_path / "first.yml"
    second = tmp_path / "second.yml"
    first.write_text(VALID)
    second.write_text(VALID)
    monkeypatch.setattr(
        checks, "iter_corpus_paths", lambda _dir: [first, second]
    )
    errors = checks.check_corpora(None)
    assert len(errors) == 1
    assert errors[0].id == "topic_flow.E002"
    assert "first.yml" in errors[0].msg
    assert "second.yml" in errors[0].msg


def test_check_passes_for_distinct_keys(tmp_path, monkeypatch):
    # Same content but different (court, topic, role) must NOT collide.
    first = tmp_path / "first.yml"
    second = tmp_path / "second.yml"
    first.write_text(VALID)
    second.write_text(VALID.replace("test-court", "other-court"))
    monkeypatch.setattr(
        checks, "iter_corpus_paths", lambda _dir: [first, second]
    )
    assert checks.check_corpora(None) == []
