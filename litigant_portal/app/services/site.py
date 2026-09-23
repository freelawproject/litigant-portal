from django.db import transaction

from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.models import Court, Site
from litigant_portal.app.selectors.site import site_get

from .utils import busts_cache


@busts_cache(SITE_CACHE_KEY)
@transaction.atomic
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
    """
    Update court metadata and application settings together.
    """
    site = site_get()
    metadata = {
        "court_name": court_name,
        "jurisdiction_level": jurisdiction_level,
        "state": state,
        "official_url": official_url,
        "official_resources_url": official_resources_url,
    }
    court, _ = Court.objects.update_or_create(
        **({"pk": site.court_id} if site.court_id else {"slug": "site"}),
        defaults=metadata,
        create_defaults={**metadata, "name": court_name},
    )
    site.court = court
    site.fast_model = fast_model
    site.assistant_model = assistant_model
    site.save(
        update_fields=["court", "fast_model", "assistant_model", "updated_at"]
    )
    return site
