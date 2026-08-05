from django.core.cache import cache

from litigant_portal.app.cache import TOPIC_LIST_CACHE_KEY
from litigant_portal.app.models import Topic


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
