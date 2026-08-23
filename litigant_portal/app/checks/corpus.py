"""Django system checks for the corpus in ``litigant_portal/corpus/``."""

from django.core.checks import Error, Tags, register

from litigant_portal.app.selectors.corpus import (
    check_corpus_directory_structure,
    corpus_load,
)


@register(Tags.compatibility)
def check_corpus(app_configs, **kwargs):
    """Surface an invalid corpus as a deploy-time error."""
    try:
        check_corpus_directory_structure()
        corpus_load()
    except ValueError as exc:
        return [
            Error(str(exc), id="corpus.E001", obj="litigant_portal/corpus")
        ]
    return []
