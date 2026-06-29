"""Django system check that validates every Topic Flow corpus at startup.

The registry skips bad corpora gracefully at runtime; this is the loud
counterpart — a malformed ``content/*.yml`` surfaces as a deploy-time error
(``manage.py check``) rather than a silently missing flow.
"""

from pathlib import Path

from django.core.checks import Error, Tags, register

from litigant_portal.app.topic_flow.loader import (
    CorpusLoader,
    CorpusValidationError,
)
from litigant_portal.app.topic_flow.registry import (
    CONTENT_DIR,
    iter_corpus_paths,
)


@register(Tags.compatibility)
def check_corpora(app_configs, **kwargs):
    errors = []
    seen: dict[tuple[str, str, str], Path] = {}
    for path in iter_corpus_paths(CONTENT_DIR):
        try:
            corpus = CorpusLoader.load(path)
        except CorpusValidationError as exc:
            errors.append(
                Error(
                    str(exc),
                    hint="Fix the corpus YAML or rename it with a leading "
                    "underscore to exclude it from the registry.",
                    id="topic_flow.E001",
                    obj=str(path),
                )
            )
            continue
        meta = corpus.metadata
        key = (meta.court, meta.topic, meta.role)
        if key in seen:
            errors.append(
                Error(
                    f"Duplicate corpus key (court={meta.court!r}, "
                    f"topic={meta.topic!r}, role={meta.role!r}): both "
                    f"{seen[key].name} and {path.name} declare it; the "
                    "later file would silently overwrite the earlier in "
                    "the registry.",
                    hint="Each content/*.yml must declare a unique "
                    "(court, topic, role). Rename, merge, or underscore-"
                    "prefix one of the files to exclude it.",
                    id="topic_flow.E002",
                    obj=str(path),
                )
            )
        else:
            seen[key] = path
    return errors
