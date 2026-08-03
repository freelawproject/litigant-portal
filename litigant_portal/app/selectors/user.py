from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef, QuerySet

from litigant_portal.app.models import Site, SiteMembership


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


def user_is_developer(*, user) -> bool:
    """Whether a user is a developer."""
    return user.is_authenticated and user.is_staff


def user_can_manage_site(*, user, site: Site) -> bool:
    """Whether a user may read or edit ``site`` itself."""
    if user.is_staff:
        return True
    return SiteMembership.objects.filter(user=user, site=site).exists()


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
