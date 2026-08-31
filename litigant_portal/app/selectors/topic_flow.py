from django.core.cache import cache

from litigant_portal.app.cache import TOPIC_LIST_CACHE_KEY
from litigant_portal.app.models import Topic, TopicFlow, VariableAnswer


def topic_list() -> list[Topic]:
    """Topics in display order, served from cache."""
    topics = cache.get(TOPIC_LIST_CACHE_KEY)
    if topics is None:
        topics = list(Topic.objects.all())
        cache.set(TOPIC_LIST_CACHE_KEY, topics, timeout=None)
    return topics


def topic_get(*, topic_id) -> Topic:
    """A single topic (raises Topic.DoesNotExist)."""
    return Topic.objects.get(id=topic_id)


def topic_flow_list() -> list[TopicFlow]:
    """Enabled flows with their topics, in topic order then flow order."""
    return list(
        TopicFlow.objects.filter(enabled=True)
        .select_related("topic")
        .order_by("topic__order", "topic__created_at", "order", "created_at")
    )


def topic_flow_find(*, topic_slug: str, flow_slug: str) -> TopicFlow | None:
    """The enabled flow at (topic_slug, flow_slug) with its whole content
    graph prefetched, or None."""
    return (
        TopicFlow.objects.filter(
            topic__slug=topic_slug, slug=flow_slug, enabled=True
        )
        .select_related("topic")
        .prefetch_related(
            "sections",
            "links",
            "deadlines__offset_from",
            "form_conditions__form",
            "form_conditions__variable",
            "interview_pages__variables__variable__asked_when",
        )
        .first()
    )


def variable_answer_list(*, identity) -> list[VariableAnswer]:
    """An identity's answers, ordered by variable name.

    Answers to variables the corpus no longer names (``in_schema=False``)
    are left out: sync keeps those rows so a migration can move them, but
    no form references them, so no surface should show them.
    """
    return list(
        VariableAnswer.objects.filter(
            identity=identity, variable__in_schema=True
        )
        .select_related("variable")
        .order_by("variable__name")
    )


def variable_answer_map(*, identity, names: list[str]) -> dict:
    """{variable_name: value} for the given names; names with no answer are omitted.

    A cleared answer (value None) counts as no answer: this map feeds
    prefill and templates, where an absent key must stay absent rather
    than fill a blank. Excludes out-of-schema variables, as
    ``variable_answer_list`` does.
    """
    return dict(
        VariableAnswer.objects.filter(
            identity=identity,
            variable__name__in=names,
            variable__in_schema=True,
            value__isnull=False,
        ).values_list("variable__name", "value")
    )
