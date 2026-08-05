from functools import wraps

from django.core.cache import cache
from django.db import transaction
from django.db.models import Max
from django.utils.text import slugify

from litigant_portal.app.cache import TOPIC_LIST_CACHE_KEY
from litigant_portal.app.models import Topic


def busts_topic_list_cache(fn):
    """Drop the cached topic list once the surrounding transaction commits."""

    @wraps(fn)
    def wrapped(*args, **kwargs):
        result = fn(*args, **kwargs)
        transaction.on_commit(lambda: cache.delete(TOPIC_LIST_CACHE_KEY))
        return result

    return wrapped


def _topic_unique_slug(*, title: str) -> str:
    base = slugify(title)[:64] or "topic"
    slug, n = base, 2
    while Topic.objects.filter(slug=slug).exists():
        suffix = f"-{n}"
        slug, n = base[: 64 - len(suffix)] + suffix, n + 1
    return slug


@busts_topic_list_cache
def topic_create(**fields) -> Topic:
    """Create a topic, appended to the display order."""
    last = Topic.objects.aggregate(m=Max("order"))["m"]
    return Topic.objects.create(
        slug=_topic_unique_slug(title=fields["title"]),
        order=0 if last is None else last + 1,
        **fields,
    )


@busts_topic_list_cache
def topic_update(*, topic: Topic, **fields) -> Topic:
    """Update a topic's editable fields."""
    for name, value in fields.items():
        setattr(topic, name, value)
    topic.save(update_fields=[*fields, "updated_at"])
    return topic


@busts_topic_list_cache
def topic_delete(*, topic: Topic) -> None:
    topic.delete()
