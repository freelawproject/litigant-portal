from django.core.cache import cache

from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.models import Site
from litigant_portal.app.models.choices import get_default_model


def site_get() -> Site:
    """The singleton settings row, served from cache."""
    site = cache.get(SITE_CACHE_KEY)
    if site is None:
        site = Site.objects.get()
        cache.set(SITE_CACHE_KEY, site, timeout=None)
    return site


def site_get_model(*, role: str) -> str:
    """The site's AI model for a pipeline role."""
    try:
        site = site_get()
    except Site.DoesNotExist:
        return get_default_model()
    return getattr(site, f"{role}_model") or get_default_model()
