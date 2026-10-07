from django.core.cache import cache

from litigant_portal.app.cache import (
    CONTACT_LIST_CACHE_KEY,
    RESOURCE_LIST_CACHE_KEY,
    SITE_CACHE_KEY,
)
from litigant_portal.app.models import Contact, Resource, Site
from litigant_portal.app.models.choices import (
    DEFAULT_BEDROCK_MODEL,
    DEFAULT_FAST_BEDROCK_MODEL,
)

_ROLE_DEFAULT_MODELS = {"fast": DEFAULT_FAST_BEDROCK_MODEL}


def site_get() -> Site:
    """The singleton settings row, served from cache."""
    site = cache.get(SITE_CACHE_KEY)
    if site is None:
        site = Site.objects.get()
        cache.set(SITE_CACHE_KEY, site, timeout=None)
    return site


def _cached_list(key: str, model) -> list:
    rows = cache.get(key)
    if rows is None:
        rows = list(model.objects.all())
        cache.set(key, rows, timeout=None)
    return rows


# Neither list is scoped by court: the rows belong to the Site singleton's
# one court, and a multi-court sync (CORPUS_COURT unset) pools every
# court's rows into them.


def contact_list() -> list[Contact]:
    """The court's contacts, in display order, served from cache."""
    return _cached_list(CONTACT_LIST_CACHE_KEY, Contact)


def resource_list() -> list[Resource]:
    """The court's resources, in display order, served from cache."""
    return _cached_list(RESOURCE_LIST_CACHE_KEY, Resource)


def site_get_model(*, role: str) -> str:
    """The site's AI model for a pipeline role."""
    return getattr(site_get(), f"{role}_model") or _ROLE_DEFAULT_MODELS.get(
        role, DEFAULT_BEDROCK_MODEL
    )
