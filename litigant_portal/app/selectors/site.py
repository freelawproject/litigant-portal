from django.core.cache import cache

from litigant_portal.app.cache import SITE_CACHE_KEY
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


def contact_list() -> list[Contact]:
    """Court and legal-help contacts, in display order."""
    return list(Contact.objects.all())


def resource_list() -> list[Resource]:
    """External resource links, in display order."""
    return list(Resource.objects.all())


def site_get_model(*, role: str) -> str:
    """The site's AI model for a pipeline role."""
    return getattr(site_get(), f"{role}_model") or _ROLE_DEFAULT_MODELS.get(
        role, DEFAULT_BEDROCK_MODEL
    )
