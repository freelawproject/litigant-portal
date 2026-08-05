import logging

from django.contrib.auth.models import Group, Permission
from django.contrib.auth.signals import user_logged_in
from django.core.cache import cache
from django.db import DEFAULT_DB_ALIAS
from django.dispatch import receiver

from .cache import SITE_CACHE_KEY, TOPIC_LIST_CACHE_KEY
from .models import Site
from .permissions import GROUP_PERMISSIONS
from .services.user import user_identity_merge_anonymous

logger = logging.getLogger(__name__)


def ensure_site_row(sender, using=DEFAULT_DB_ALIAS, apps=None, **kwargs):
    """Guarantee the singleton site row exists, and drop the cached pickles."""
    keys = [SITE_CACHE_KEY, TOPIC_LIST_CACHE_KEY]
    try:
        cache.delete_many(keys)
    except Exception:
        logger.warning(
            "Could not clear %s after migrate; stale values may be served "
            "until the next write.",
            keys,
            exc_info=True,
        )
    site_model = apps.get_model("app", "Site") if apps else Site
    site_model.objects.using(using).get_or_create()


def ensure_permission_groups(
    sender, using=DEFAULT_DB_ALIAS, apps=None, **kwargs
):
    """After ``migrate``, guarantee the permission groups exist and hold
    their permissions.

    Relies on ``django.contrib.auth`` preceding this app in
    ``INSTALLED_APPS``. Fired from AppConfig.ready() so that is only runs
    for this app.
    """
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
