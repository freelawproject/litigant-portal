"""Django system check that validates every Topic Flow corpus at startup.

The registry skips bad corpora gracefully at runtime; this is the loud
counterpart — a malformed ``content/*.yml`` surfaces as a deploy-time error
(``manage.py check``) rather than a silently missing flow.
"""

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
    for path in iter_corpus_paths(CONTENT_DIR):
        try:
            CorpusLoader.load(path)
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
    return errors
