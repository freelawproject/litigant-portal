from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.models import Site
from litigant_portal.app.selectors.site import site_get

from .utils import busts_cache


@busts_cache(SITE_CACHE_KEY)
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
