from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Exists, OuterRef, QuerySet
from django.forms.models import model_to_dict

from litigant_portal.app.models import Site, SiteMembership, Topic
from litigant_portal.app.models.choices import get_default_model

ACTIVE_SITE_CACHE_KEY = "active_site_data"
ACTIVE_SITE_TOPICS_CACHE_KEY = "active_site_topics"


def site_get_active_data() -> dict | None:
    """The cached active site's settings."""
    data = cache.get(ACTIVE_SITE_CACHE_KEY)
    if data is None:
        site = Site.objects.filter(active=True).first()
        if site is None:
            return None
        data = {"id": str(site.id)} | model_to_dict(site)
        cache.set(ACTIVE_SITE_CACHE_KEY, data, timeout=None)
    return data


def site_get_active_topics() -> list[dict]:
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


def site_get_model(*, role: str) -> str:
    """The active site's AI model for a pipeline role."""
    data = site_get_active_data() or {}
    return data.get(f"{role}_model") or get_default_model()


def site_list() -> QuerySet[Site]:
    """All site settings rows, oldest first."""
    return Site.objects.order_by("created_at")


def site_get(*, site_id) -> Site:
    """A single site row by id (raises Site.DoesNotExist)."""
    return Site.objects.get(id=site_id)


def site_get_active() -> Site:
    """The active site row (raises Site.DoesNotExist)."""
    return Site.objects.get(active=True)


def topic_list(*, site: Site) -> QuerySet[Topic]:
    """A site's topics in display order (the model's default ordering)."""
    return site.topics.all()


def topic_get(*, site: Site, topic_id) -> Topic:
    """A single topic within ``site`` (raises Topic.DoesNotExist)."""
    return site.topics.get(id=topic_id)


def user_list(*, search: str = "", site: Site | None = None) -> QuerySet[User]:
    """Users for the admin users tab, filtered by email substring.

    When ``site`` is given, each user is annotated with
    ``is_site_member`` for that site.
    """
    users = User.objects.order_by("email")
    if search:
        users = users.filter(email__icontains=search)
    if site is not None:
        users = users.annotate(
            is_site_member=Exists(
                SiteMembership.objects.filter(user=OuterRef("pk"), site=site)
            )
        )
    return users
