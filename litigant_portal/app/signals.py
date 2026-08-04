import logging

from django.contrib.auth.models import Group, Permission
from django.contrib.auth.signals import user_logged_in
from django.db import DEFAULT_DB_ALIAS
from django.db.models.signals import post_migrate
from django.dispatch import receiver

from .permissions import GROUP_PERMISSIONS
from .services.user import user_identity_merge_anonymous

logger = logging.getLogger(__name__)


@receiver(post_migrate)
def ensure_permission_groups(
    sender, using=DEFAULT_DB_ALIAS, apps=None, **kwargs
):
    """After ``migrate``, guarantee the permission groups exist and hold
    their permissions.

    Relies on ``django.contrib.auth`` preceding this app in
    ``INSTALLED_APPS``: its ``create_permissions`` receiver connects to
    ``post_migrate`` first and so runs first for the same sender, creating
    the permissions handed out here. The warning below is what surfaces
    that ordering if it ever stops holding — without it, the groups would
    be created empty and the only symptom would be a 403 for every admin.
    """
    if getattr(sender, "name", None) != "litigant_portal.app":
        return
    group_model = apps.get_model("auth", "Group") if apps else Group
    permission_model = (
        apps.get_model("auth", "Permission") if apps else Permission
    )
    for name, codenames in GROUP_PERMISSIONS.items():
        group, _ = group_model.objects.using(using).get_or_create(name=name)
        permissions = list(
            permission_model.objects.using(using).filter(
                codename__in=codenames, content_type__app_label="app"
            )
        )
        if len(permissions) != len(codenames):
            logger.warning(
                "Group %r is missing permissions: expected %s, found %s. "
                "Nobody in it will have admin access until the missing "
                "permissions exist.",
                name,
                sorted(codenames),
                sorted(p.codename for p in permissions),
            )
        # add() already skips rows the group has, and is a no-op when empty.
        group.permissions.add(*permissions)


@receiver(user_logged_in)
def merge_anonymous_identity(request, user, **kwargs):
    """On login, fold the anonymous UserIdentity into the user's identity."""
    session_key = request.session.pop("_anonymous_session_key", None)
    if session_key:
        user_identity_merge_anonymous(user=user, session_key=session_key)
