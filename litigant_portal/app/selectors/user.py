from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef, QuerySet

from litigant_portal.app.models import Site, SiteMembership


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
