"""
Host-owned configuration choices for the new agent's development page.
"""

from django.conf import settings

from litigant_portal.app.selectors.corpus import (
    corpus_load_courts,
    corpus_load_topics,
)


def agent_scope_choices() -> tuple[list[dict], list[dict]]:
    """
    List court/topic pairs available to this deployment.
    """
    courts = [
        {"slug": slug, "name": court.name}
        for slug, court in corpus_load_courts().items()
        if settings.CORPUS_COURT is None or slug == settings.CORPUS_COURT
    ]
    allowed_courts = {court["slug"] for court in courts}
    topics = [
        {"court": court, "slug": slug, "title": topic.title}
        for (court, slug), topic in corpus_load_topics().items()
        if court in allowed_courts
    ]
    return courts, topics
