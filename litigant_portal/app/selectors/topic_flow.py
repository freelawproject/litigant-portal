from django.core.cache import cache
from django.db.models import QuerySet
from django.forms.models import model_to_dict

from litigant_portal.app.models import Site, Topic

ACTIVE_SITE_TOPICS_CACHE_KEY = "active_site_topics"


def topic_list(*, site: Site) -> QuerySet[Topic]:
    """A site's topics in display order (the model's default ordering)."""
    return site.topics.all()


def topic_list_active() -> list[dict]:
    """The active site's cached topics as plain dicts in display order."""
    data = cache.get(ACTIVE_SITE_TOPICS_CACHE_KEY)
    if data is None:
        site = Site.objects.filter(active=True).first()
        if site is None:
            return []
        data = [
            {"id": str(topic.id)}
            | model_to_dict(topic)
            | {"site": str(site.id)}
            for topic in topic_list(site=site)
        ]
        cache.set(ACTIVE_SITE_TOPICS_CACHE_KEY, data, timeout=None)
    return data


def topic_get(*, site: Site, topic_id) -> Topic:
    """A single topic within ``site`` (raises Topic.DoesNotExist)."""
    return site.topics.get(id=topic_id)
