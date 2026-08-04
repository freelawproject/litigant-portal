from django.core.cache import cache
from django.db.models import Max
from django.utils.text import slugify

from litigant_portal.app.models import Site, Topic
from litigant_portal.app.selectors.topic_flow import (
    ACTIVE_SITE_TOPICS_CACHE_KEY,
)


def _topic_unique_slug(*, site: Site, title: str) -> str:
    base = slugify(title)[:64] or "topic"
    slug, n = base, 2
    while Topic.objects.filter(site=site, slug=slug).exists():
        suffix = f"-{n}"
        slug, n = base[: 64 - len(suffix)] + suffix, n + 1
    return slug


def topic_create(*, site: Site, **fields) -> Topic:
    """Create a topic in ``site``."""
    last = site.topics.aggregate(m=Max("order"))["m"]
    topic = Topic.objects.create(
        site=site,
        slug=_topic_unique_slug(site=site, title=fields["title"]),
        order=0 if last is None else last + 1,
        **fields,
    )
    cache.delete(ACTIVE_SITE_TOPICS_CACHE_KEY)
    return topic


def topic_update(*, topic: Topic, **fields) -> Topic:
    """Update a topic's editable fields."""
    for name, value in fields.items():
        setattr(topic, name, value)
    topic.save(update_fields=[*fields, "updated_at"])
    cache.delete(ACTIVE_SITE_TOPICS_CACHE_KEY)
    return topic


def topic_delete(*, topic: Topic) -> None:
    topic.delete()
    cache.delete(ACTIVE_SITE_TOPICS_CACHE_KEY)
