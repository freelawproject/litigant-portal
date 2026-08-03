from django.db.models import QuerySet

from litigant_portal.app.models import Site, Topic


def topic_list(*, site: Site) -> QuerySet[Topic]:
    """A site's topics in display order (the model's default ordering)."""
    return site.topics.all()


def topic_get(*, site: Site, topic_id) -> Topic:
    """A single topic within ``site`` (raises Topic.DoesNotExist)."""
    return site.topics.get(id=topic_id)
