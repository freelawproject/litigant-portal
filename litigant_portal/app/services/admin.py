from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Max
from django.utils.text import slugify

from litigant_portal.app.models import Site, SiteMembership, Topic


def user_can_access_admin(*, user) -> bool:
    """Whether a user may see the admin panel at all.

    Developers (User.is_staff) always can; everyone else needs a membership in
    the currently active site.
    """
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return SiteMembership.objects.filter(user=user, site__active=True).exists()


def site_membership_toggle(*, user: User, site: Site) -> bool:
    """Flip a user's membership in ``site``; returns the new state."""
    membership = SiteMembership.objects.filter(user=user, site=site).first()
    if membership:
        membership.delete()
        return False
    SiteMembership.objects.create(user=user, site=site)
    return True


def user_developer_toggle(*, user: User) -> bool:
    """Flip a user's developer (staff) flag; returns the new state."""
    user.is_staff = not user.is_staff
    user.save(update_fields=["is_staff"])
    return user.is_staff


def site_activate(*, site: Site) -> Site:
    """Make ``site`` the single active site row."""
    with transaction.atomic():
        Site.objects.filter(active=True).exclude(id=site.id).update(
            active=False
        )
        if not site.active:
            site.active = True
            site.save(update_fields=["active", "updated_at"])
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
) -> Site:
    """Update a site row's editable fields."""
    site.name = name
    site.court_name = court_name
    site.jurisdiction_level = jurisdiction_level
    site.state = state
    site.official_url = official_url
    site.official_resources_url = official_resources_url
    site.save(
        update_fields=[
            "name",
            "court_name",
            "jurisdiction_level",
            "state",
            "official_url",
            "official_resources_url",
            "updated_at",
        ]
    )
    return site


def _topic_unique_slug(*, site: Site, title: str) -> str:
    base = slugify(title)[:64] or "topic"
    slug, n = base, 2
    while Topic.objects.filter(site=site, slug=slug).exists():
        suffix = f"-{n}"
        slug, n = base[: 64 - len(suffix)] + suffix, n + 1
    return slug


def topic_create(*, site: Site, **fields) -> Topic:
    """Create a topic in ``site``."""
    last = site.topics.aggregate(m=Max("order"))["m"]
    return Topic.objects.create(
        site=site,
        slug=_topic_unique_slug(site=site, title=fields["title"]),
        order=0 if last is None else last + 1,
        **fields,
    )


def topic_update(*, topic: Topic, **fields) -> Topic:
    """Update a topic's editable fields."""
    for name, value in fields.items():
        setattr(topic, name, value)
    topic.save(update_fields=[*fields, "updated_at"])
    return topic


def topic_delete(*, topic: Topic) -> None:
    topic.delete()
