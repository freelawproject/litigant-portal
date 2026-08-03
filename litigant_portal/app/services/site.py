from django.core.cache import cache
from django.db import transaction

from litigant_portal.app.models import Site
from litigant_portal.app.selectors.site import (
    ACTIVE_SITE_CACHE_KEY,
    ACTIVE_SITE_TOPICS_CACHE_KEY,
)


def site_activate(*, site: Site) -> Site:
    """Make ``site`` the single active site row."""
    with transaction.atomic():
        Site.objects.filter(active=True).exclude(id=site.id).update(
            active=False
        )
        if not site.active:
            site.active = True
            site.save(update_fields=["active", "updated_at"])
    cache.delete(ACTIVE_SITE_CACHE_KEY)
    cache.delete(ACTIVE_SITE_TOPICS_CACHE_KEY)
    return site


def site_update(
    *,
    site: Site,
    name: str,
    court_name: str = "",
    jurisdiction_level: str = "",
    state: str = "",
    official_url: str = "",
    official_resources_url: str = "",
    fast_model: str = "",
    assistant_model: str = "",
) -> Site:
    """Update a site row's editable fields."""
    site.name = name
    site.court_name = court_name
    site.jurisdiction_level = jurisdiction_level
    site.state = state
    site.official_url = official_url
    site.official_resources_url = official_resources_url
    site.fast_model = fast_model
    site.assistant_model = assistant_model
    site.save(
        update_fields=[
            "name",
            "court_name",
            "jurisdiction_level",
            "state",
            "official_url",
            "official_resources_url",
            "fast_model",
            "assistant_model",
            "updated_at",
        ]
    )
    cache.delete(ACTIVE_SITE_CACHE_KEY)
    return site
