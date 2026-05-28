"""Discover and index Topic Flow corpora on disk.

Corpora live as ``content/*.yml`` at the repo root. Files whose name starts
with ``_`` (e.g. ``_test_fixture.yml``) are skipped — a convention for
fixtures and drafts that shouldn't render as real flows. Each valid corpus is
indexed by its ``(court, topic, role)`` key.

The registry is **graceful** at runtime: a corpus that fails validation is
logged and skipped so one bad file can't take down every flow. The loud signal
is the Django system check in ``checks.py``, which surfaces the same failures
as startup errors.
"""

import logging
from pathlib import Path

from litigant_portal.app.topic_flow.loader import (
    CorpusLoader,
    CorpusValidationError,
)
from litigant_portal.app.topic_flow.schema import Corpus

logger = logging.getLogger(__name__)

CONTENT_DIR = Path(__file__).resolve().parents[3] / "content"


def iter_corpus_paths(content_dir: Path) -> list[Path]:
    """Return registry-eligible corpus paths (``*.yml``, no ``_`` prefix)."""
    return [
        path
        for path in sorted(content_dir.glob("*.yml"))
        if not path.name.startswith("_")
    ]


class CorpusRegistry:
    """Lazily loads and indexes corpora by ``(court, topic, role)``."""

    def __init__(self, content_dir: Path | None = None):
        self._content_dir = Path(content_dir) if content_dir else CONTENT_DIR
        self._index: dict[tuple[str, str, str], Corpus] = {}
        self._loaded = False

    def load(self) -> "CorpusRegistry":
        if self._loaded:
            return self
        index: dict[tuple[str, str, str], Corpus] = {}
        for path in iter_corpus_paths(self._content_dir):
            try:
                corpus = CorpusLoader.load(path)
            except CorpusValidationError as exc:
                logger.warning("Skipping invalid corpus: %s", exc)
                continue
            meta = corpus.metadata
            index[(meta.court, meta.topic, meta.role)] = corpus
        self._index = index
        self._loaded = True
        return self

    def get(self, court: str, topic: str, role: str) -> Corpus | None:
        self.load()
        return self._index.get((court, topic, role))

    def keys(self) -> list[tuple[str, str, str]]:
        self.load()
        return list(self._index)


# Module-level default over the repo's content/ directory.
registry = CorpusRegistry()
