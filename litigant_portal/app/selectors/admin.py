from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef, QuerySet

from litigant_portal.app.models import Site, SiteMembership, Topic


def site_list() -> QuerySet[Site]:
    """All site settings rows, oldest first."""
    return Site.objects.order_by("created_at")


def site_get(*, site_id) -> Site:
    """A single site row by id (raises Site.DoesNotExist)."""
    return Site.objects.get(id=site_id)


def site_get_active() -> Site:
    """The active site row (raises Site.DoesNotExist)."""
    return Site.objects.get(active=True)


def topic_list(*, site: Site) -> QuerySet[Topic]:
    """A site's topics in display order (the model's default ordering)."""
    return site.topics.all()


def topic_get(*, site: Site, topic_id) -> Topic:
    """A single topic within ``site`` (raises Topic.DoesNotExist)."""
    return site.topics.get(id=topic_id)


def user_list(*, search: str = "", site: Site | None = None) -> QuerySet[User]:
    """Users for the admin users tab, filtered by email substring.

    When ``site`` is given, each user is annotated with
    ``is_site_member`` for that site.
    """
    users = User.objects.order_by("email")
    if search:
        users = users.filter(email__icontains=search)
    if site is not None:
        users = users.annotate(
            is_site_member=Exists(
                SiteMembership.objects.filter(user=OuterRef("pk"), site=site)
            )
        )
    return users
