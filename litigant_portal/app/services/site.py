from functools import wraps

from django.core.cache import cache
from django.db import transaction

from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.models import Site


def busts_site_cache(fn):
    """Drop the cached site row once the surrounding transaction commits."""

    @wraps(fn)
    def wrapped(*args, **kwargs):
        result = fn(*args, **kwargs)
        transaction.on_commit(lambda: cache.delete(SITE_CACHE_KEY))
        return result

    return wrapped


@busts_site_cache
def site_update(
    *,
    court_name: str = "",
    jurisdiction_level: str = "",
    state: str = "",
    official_url: str = "",
    official_resources_url: str = "",
    fast_model: str = "",
    assistant_model: str = "",
) -> Site:
    """Update the site's editable fields."""
    site = site_get()
    site.court_name = court_name
    site.jurisdiction_level = jurisdiction_level
    site.state = state
    site.official_url = official_url
    site.official_resources_url = official_resources_url
    site.fast_model = fast_model
    site.assistant_model = assistant_model
    site.save(
        update_fields=[
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
    return site
