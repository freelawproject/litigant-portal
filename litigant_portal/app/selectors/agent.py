"""
Host-owned configuration choices for the new agent's development page.
"""

from django.conf import settings

from litigant_portal.app.selectors.corpus import (
    corpus_load_courts,
    corpus_load_topics,
)
from lp_agent.adapters.catalog import Court
from lp_agent.types import Choice


def agent_scope_choices() -> tuple[Court, ...]:
    """
    List court/topic pairs available to this deployment.
    """
    topics = corpus_load_topics()
    return tuple(
        Court(
            choice_id=slug,
            label=court.name,
            topics=tuple(
                Choice(choice_id=topic_slug, label=topic.title)
                for (court_slug, topic_slug), topic in topics.items()
                if court_slug == slug
            ),
        )
        for slug, court in corpus_load_courts().items()
        if settings.CORPUS_COURT is None or slug == settings.CORPUS_COURT
    )
