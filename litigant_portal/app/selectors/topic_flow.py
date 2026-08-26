from django.core.cache import cache

from litigant_portal.app.cache import TOPIC_LIST_CACHE_KEY
from litigant_portal.app.models import Topic, VariableAnswer


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
