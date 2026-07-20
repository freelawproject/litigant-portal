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


# --- tracks_for: omni-court topic → track links (chat handoff, #633) ---


def test_tracks_for_bridges_chat_underscore_slug(tmp_path):
    # Chat topics use underscores (adult_name_change); corpora may use either.
    (tmp_path / "real.yml").write_text(VALID)
    registry = CorpusRegistry(content_dir=tmp_path)
    tracks = registry.tracks_for("test_topic")
    assert [(t["court"], t["topic"], t["role"]) for t in tracks] == [
        FIXTURE_KEY
    ]


def test_tracks_for_normalizes_both_sides(tmp_path):
    # Dashed chat slug must match an underscored corpus topic too.
    (tmp_path / "real.yml").write_text(VALID)
    registry = CorpusRegistry(content_dir=tmp_path)
    assert registry.tracks_for("test-topic") != []


def test_tracks_for_unknown_topic_returns_empty(tmp_path):
    (tmp_path / "real.yml").write_text(VALID)
    registry = CorpusRegistry(content_dir=tmp_path)
    assert registry.tracks_for("eviction") == []


def test_tracks_for_carries_label_and_title(tmp_path):
    (tmp_path / "real.yml").write_text(VALID)
    registry = CorpusRegistry(content_dir=tmp_path)
    track = registry.tracks_for("test_topic")[0]
    assert track["label"] == "Petitioner"
    assert track["title"] == registry.get(*FIXTURE_KEY).metadata.title


def test_tracks_for_returns_all_tracks_in_file_order(tmp_path):
    (tmp_path / "a.yml").write_text(VALID)
    (tmp_path / "b.yml").write_text(
        VALID.replace("role: petitioner", "role: respondent")
    )
    registry = CorpusRegistry(content_dir=tmp_path)
    roles = [t["role"] for t in registry.tracks_for("test_topic")]
    assert roles == ["petitioner", "respondent"]


def test_tracks_for_orders_by_order_field(tmp_path):
    # `order:` lets authors control which track renders first, independent of
    # filename (e.g. Tenant before Landlord on eviction). Here the
    # alphabetically-first file (a.yml) carries the *higher* order, so it must
    # render second — proving order wins over the file/alpha fallback.
    (tmp_path / "a.yml").write_text(
        VALID.replace("role: petitioner", "role: landlord\n  order: 2")
    )
    (tmp_path / "b.yml").write_text(
        VALID.replace("role: petitioner", "role: tenant\n  order: 1")
    )
    registry = CorpusRegistry(content_dir=tmp_path)
    roles = [t["role"] for t in registry.tracks_for("test_topic")]
    assert roles == ["tenant", "landlord"]


def test_tracks_for_ordered_tracks_precede_unordered(tmp_path):
    # Mixed: a corpus with an explicit order sorts ahead of one without, and
    # the unordered track keeps its natural file position among peers.
    (tmp_path / "a.yml").write_text(VALID)  # petitioner, no order
    (tmp_path / "b.yml").write_text(
        VALID.replace("role: petitioner", "role: respondent\n  order: 1")
    )
    registry = CorpusRegistry(content_dir=tmp_path)
    roles = [t["role"] for t in registry.tracks_for("test_topic")]
    assert roles == ["respondent", "petitioner"]


def test_all_tracks_lists_every_corpus_ordered(tmp_path):
    (tmp_path / "a.yml").write_text(VALID)
    # Same topic, second role, explicit order: sorts ahead of unordered.
    other = VALID.replace(
        "  role: petitioner", "  role: respondent\n  order: 1"
    )
    (tmp_path / "b.yml").write_text(other)
    registry = CorpusRegistry(content_dir=tmp_path)
    tracks = registry.all_tracks()
    assert [t["role"] for t in tracks] == ["respondent", "petitioner"]
    first = tracks[0]
    assert first["court"] == "test-court"
    assert first["topic"] == "test_topic"
    # Self-describing label in a mixed, topic-less list: the corpus title.
    assert first["label"] == first["title"]


def test_all_tracks_empty_registry(tmp_path):
    registry = CorpusRegistry(content_dir=tmp_path)
    assert registry.all_tracks() == []
