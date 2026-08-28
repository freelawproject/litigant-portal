from django.core.cache import cache

from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.models import Site
from litigant_portal.app.models.choices import DEFAULT_BEDROCK_MODEL


def site_get() -> Site:
    """The singleton settings row, served from cache."""
    site = cache.get(SITE_CACHE_KEY)
    if site is None:
        site = Site.objects.get()
        cache.set(SITE_CACHE_KEY, site, timeout=None)
    return site


def site_get_model(*, role: str) -> str:
    """The site's AI model for a pipeline role."""
    return getattr(site_get(), f"{role}_model") or DEFAULT_BEDROCK_MODEL
