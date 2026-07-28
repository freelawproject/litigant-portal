import vobject
from django.core.cache import cache
from django.db import transaction
from django.db.models import Max

from litigant_portal.app.models import Contact, Resource, Site
from litigant_portal.app.selectors.site import (
    SITE_CACHE_KEY,
    contact_list,
    resource_list,
)
from litigant_portal.app.services.utils import row_move


def site_save(*, site: Site, update_fields: list[str]) -> Site:
    """Save the site and bust its cache so the next read re-stashes."""
    site.save(update_fields=[*update_fields, "updated_at"])
    transaction.on_commit(lambda: cache.delete(SITE_CACHE_KEY))
    return site


def site_court_details_update(
    *,
    site: Site,
    court_name: str = "",
    jurisdiction_level: str = "",
    state: str = "",
    official_url: str = "",
    official_resources_url: str = "",
) -> Site:
    """Update the site's court detail fields."""
    site.court_name = court_name
    site.jurisdiction_level = jurisdiction_level
    site.state = state
    site.official_url = official_url
    site.official_resources_url = official_resources_url
    return site_save(
        site=site,
        update_fields=[
            "court_name",
            "jurisdiction_level",
            "state",
            "official_url",
            "official_resources_url",
        ],
    )


def site_models_update(
    *, site: Site, fast_model: str = "", assistant_model: str = ""
) -> Site:
    """Update the site's AI model selections."""
    site.fast_model = fast_model
    site.assistant_model = assistant_model
    return site_save(
        site=site, update_fields=["fast_model", "assistant_model"]
    )


def contact_create(**fields) -> Contact:
    """Create a contact, appended to the display order."""
    last = Contact.objects.aggregate(m=Max("order"))["m"]
    return Contact.objects.create(
        order=0 if last is None else last + 1, **fields
    )


def contact_update(*, contact: Contact, **fields) -> Contact:
    """Update a contact's editable fields."""
    for name, value in fields.items():
        setattr(contact, name, value)
    contact.save(update_fields=[*fields, "updated_at"])
    return contact


def contact_delete(*, contact: Contact) -> None:
    contact.delete()


def contact_move(*, contact: Contact, direction: str) -> None:
    """Move a contact one step up or down in the display order."""
    with transaction.atomic():
        row_move(list(contact_list()), contact, direction)


def resource_create(**fields) -> Resource:
    """Create a resource, appended to the display order."""
    last = Resource.objects.aggregate(m=Max("order"))["m"]
    return Resource.objects.create(
        order=0 if last is None else last + 1, **fields
    )


def resource_update(*, resource: Resource, **fields) -> Resource:
    """Update a resource's editable fields."""
    for name, value in fields.items():
        setattr(resource, name, value)
    resource.save(update_fields=[*fields, "updated_at"])
    return resource


def resource_delete(*, resource: Resource) -> None:
    resource.delete()


def resource_move(*, resource: Resource, direction: str) -> None:
    """Move a resource one step up or down in the display order."""
    with transaction.atomic():
        row_move(list(resource_list()), resource, direction)


def contact_list_vcf() -> str:
    """The site's contacts as a vCard (``.vcf``) string."""
    out = []
    for contact in contact_list():
        vcard = vobject.vCard()
        vcard.add("uid").value = f"{contact.id}@litigantportal.com"
        vcard.add("fn").value = contact.name
        # ORG (a structured/list value): our contacts are offices, so a
        # phone imports them as an organization card, not a person.
        vcard.add("org").value = [contact.name]
        if contact.phone:
            vcard.add("tel").value = contact.phone
        if contact.email:
            vcard.add("email").value = contact.email
        if contact.url:
            vcard.add("url").value = contact.url
        if contact.note:
            vcard.add("note").value = contact.note
        out.append(vcard.serialize())
    return "".join(out)
