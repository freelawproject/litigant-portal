"""Django system checks for the docassemble handoff settings.

The handoff fails safe at request time (a half-configured prefill falls back
to the plain interview; an unconfigured docassemble hides the button), so
neither state is loud where an operator looks. These are the loud
counterparts, surfacing once at deploy time (#879): W001 for a key without
its API root, W002 naming the flows whose handoff is hidden because no
docassemble is configured at all.
"""

from django.conf import settings
from django.core.checks import Tags, Warning, register

from litigant_portal.app.services.docassemble import docassemble_configured
from litigant_portal.app.topic_flow.loader import (
    CorpusLoader,
    CorpusValidationError,
)
from litigant_portal.app.topic_flow.prefill import interview_target
from litigant_portal.app.topic_flow.registry import (
    CONTENT_DIR,
    iter_corpus_paths,
)


@register(Tags.compatibility)
def check_docassemble_settings(app_configs, **kwargs):
    if settings.DOCASSEMBLE_API_KEY and not settings.DOCASSEMBLE_BASE_URL:
        return [
            Warning(
                "DOCASSEMBLE_API_KEY is set but DOCASSEMBLE_BASE_URL is "
                "not, so every prefill attempt fails and falls back to the "
                "plain, unprefilled interview.",
                hint="Set DOCASSEMBLE_BASE_URL to the API root the key "
                "belongs to, or unset the key.",
                id="docassemble.W001",
            )
        ]
    return []


@register(Tags.compatibility)
def check_unservable_handoffs(app_configs, **kwargs):
    if docassemble_configured():
        return []
    affected = []
    for path in iter_corpus_paths(CONTENT_DIR):
        try:
            corpus = CorpusLoader.load(path)
        except CorpusValidationError:
            # topic_flow.E001 reports it; not this check's business.
            continue
        if interview_target(corpus) is not None:
            meta = corpus.metadata
            affected.append(f"{meta.court}/{meta.topic}/{meta.role}")
    if not affected:
        return []
    return [
        Warning(
            "No docassemble configured; the interview handoff is hidden "
            f"on: {', '.join(sorted(affected))}.",
            hint="Set DOCASSEMBLE_BASE_URL to enable it.",
            id="docassemble.W002",
        )
    ]
