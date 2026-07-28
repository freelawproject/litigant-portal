from django.core.cache import cache
from django.db.models import QuerySet

from litigant_portal.app.models import Contact, Resource, Site
from litigant_portal.app.models.choices import get_default_model

SITE_CACHE_KEY = "site"


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


def contact_list() -> QuerySet[Contact]:
    """The site's contacts in display order."""
    return Contact.objects.order_by("order", "created_at")


def contact_get(*, contact_id) -> Contact:
    """A single contact."""
    return Contact.objects.get(id=contact_id)


def contact_name_taken(*, name: str, exclude_id=None) -> bool:
    """Whether a contact with this name already exists (names are unique)."""
    contacts = Contact.objects.filter(name=name)
    if exclude_id is not None:
        contacts = contacts.exclude(id=exclude_id)
    return contacts.exists()


def resource_list() -> QuerySet[Resource]:
    """The site's resources in display order."""
    return Resource.objects.order_by("order", "created_at")


def resource_get(*, resource_id) -> Resource:
    """A single resource."""
    return Resource.objects.get(id=resource_id)


def resource_label_taken(*, label: str, exclude_id=None) -> bool:
    """Whether a resource with this label already exists (labels are
    unique)."""
    resources = Resource.objects.filter(label=label)
    if exclude_id is not None:
        resources = resources.exclude(id=exclude_id)
    return resources.exists()
