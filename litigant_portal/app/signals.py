from django.contrib.auth.models import Group, Permission
from django.contrib.auth.signals import user_logged_in
from django.db import DEFAULT_DB_ALIAS
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .models import Site
from .services.user import (
    ADMINS_GROUP,
    DEVELOPERS_GROUP,
    user_identity_merge_anonymous,
)


@receiver(post_migrate)
def ensure_site_row(sender, using=DEFAULT_DB_ALIAS, apps=None, **kwargs):
    """Guarantee the singleton site row exists."""
    if getattr(sender, "name", None) != "litigant_portal.app":
        return
    site_model = apps.get_model("app", "Site") if apps else Site
    if not site_model.objects.using(using).exists():
        site_model.objects.using(using).create()


@receiver(post_migrate)
def ensure_permission_groups(
    sender, using=DEFAULT_DB_ALIAS, apps=None, **kwargs
):
    """After ``migrate``, guarantee the permission groups exist."""
    if getattr(sender, "name", None) != "litigant_portal.app":
        return
    group_model = apps.get_model("auth", "Group") if apps else Group
    permission_model = (
        apps.get_model("auth", "Permission") if apps else Permission
    )
    group_codenames = {
        ADMINS_GROUP: ["manage_site"],
        DEVELOPERS_GROUP: ["manage_site", "manage_developers"],
    }
    for name, codenames in group_codenames.items():
        group, _ = group_model.objects.using(using).get_or_create(name=name)
        permissions = permission_model.objects.using(using).filter(
            codename__in=codenames, content_type__app_label="app"
        )
        for permission in permissions:
            if not group.permissions.filter(pk=permission.pk).exists():
                group.permissions.add(permission)


@receiver(user_logged_in)
def merge_anonymous_identity(request, user, **kwargs):
    """On login, fold the anonymous UserIdentity into the user's identity."""
    session_key = request.session.pop("_anonymous_session_key", None)
    if session_key:
        user_identity_merge_anonymous(user=user, session_key=session_key)
