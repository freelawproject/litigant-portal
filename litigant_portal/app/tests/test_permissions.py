"""Tests for the tiered admin roles (#1135).

Four tiers: Superuser → FLP Staff → Court Admin → App user. Covers the
groups the post_migrate receiver provisions, how an account's tier is read,
and the view guards that rest on both. The guards are a security boundary,
so the negative cases (no permission -> 403) matter more than the happy
paths.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase

from litigant_portal.app.permissions import (
    COURT_ADMINS_GROUP,
    FLP_STAFF_GROUP,
    Tier,
)
from litigant_portal.app.selectors.user import user_list, user_tier

User = get_user_model()


def client_for(user=None) -> Client:
    """A test client past the dev-only site-password gate."""
    client = Client(SERVER_NAME="localhost")
    if user is not None:
        client.force_login(user)
    session = client.session
    session["site_password_ok"] = True
    session.save()
    return client


def reload(user: User) -> User:
    """Re-fetch a user so ``has_perm`` doesn't answer from its cache."""
    return User.objects.get(pk=user.pk)


def join(user: User, group_name: str) -> User:
    """Add ``user`` to a group and return a fresh copy."""
    user.groups.add(Group.objects.get(name=group_name))
    return reload(user)


@pytest.mark.postgres
class PermissionGroupTests(TestCase):
    """The groups the post_migrate receiver guarantees."""

    def test_only_the_two_role_groups_exist(self):
        self.assertEqual(
            sorted(Group.objects.values_list("name", flat=True)),
            sorted([COURT_ADMINS_GROUP, FLP_STAFF_GROUP]),
        )

    def test_flp_staff_manage_the_site_and_app_users(self):
        group = Group.objects.get(name=FLP_STAFF_GROUP)
        self.assertEqual(
            sorted(p.codename for p in group.permissions.all()),
            ["manage_app_users", "manage_site"],
        )

    def test_court_admins_manage_app_users_only(self):
        group = Group.objects.get(name=COURT_ADMINS_GROUP)
        self.assertEqual(
            [p.codename for p in group.permissions.all()],
            ["manage_app_users"],
        )

    def test_permissions_belong_to_the_app_label(self):
        # The guards check "app.manage_site"; a permission created under
        # another content type would never match.
        codenames = set(
            Permission.objects.filter(
                content_type__app_label="app",
                codename__startswith="manage_",
            ).values_list("codename", flat=True)
        )
        self.assertEqual(codenames, {"manage_site", "manage_app_users"})


@pytest.mark.postgres
class UserTierTests(TestCase):
    def test_each_account_kind_reads_as_its_tier(self):
        superuser = User.objects.create_superuser(username="s", password="p")
        staff = join(User.objects.create_user(username="f"), FLP_STAFF_GROUP)
        court = join(
            User.objects.create_user(username="c"), COURT_ADMINS_GROUP
        )
        app_user = User.objects.create_user(username="u")
        cases = [
            (superuser, Tier.SUPERUSER),
            (staff, Tier.FLP_STAFF),
            (court, Tier.COURT_ADMIN),
            (app_user, Tier.APP_USER),
        ]
        for user, tier in cases:
            with self.subTest(user=user.username):
                self.assertEqual(user_tier(user=user), tier)

    def test_django_admin_staff_rank_as_flp_staff_without_the_group(self):
        # is_staff opens Django admin, where every transcript is readable,
        # so it can never sit low enough for a Court Admin to reach.
        user = User.objects.create_user(username="st", is_staff=True)
        self.assertEqual(user_tier(user=user), Tier.FLP_STAFF)

    def test_the_highest_role_wins(self):
        user = User.objects.create_user(username="both")
        join(user, COURT_ADMINS_GROUP)
        user = join(user, FLP_STAFF_GROUP)
        self.assertEqual(user_tier(user=user), Tier.FLP_STAFF)

    def test_a_disabled_account_keeps_its_tier(self):
        # has_perm answers False for inactive users, so the tier must come
        # from the account itself or a disabled FLP Staff account would
        # drop to a tier a Court Admin can reach.
        user = join(User.objects.create_user(username="f"), FLP_STAFF_GROUP)
        user.is_active = False
        user.save()
        self.assertEqual(user_tier(user=reload(user)), Tier.FLP_STAFF)

    def test_user_list_annotates_role_membership(self):
        user = join(User.objects.create_user(username="c"), COURT_ADMINS_GROUP)
        row = user_list().get(pk=user.pk)
        self.assertTrue(row.is_court_admin_member)
        self.assertFalse(row.is_flp_staff_member)


@pytest.mark.postgres
class SuperuserTests(TestCase):
    """Superusers hold every permission implicitly, without a group.

    Worth pinning: ``bootstrap_superuser`` creates the account that has to
    be able to grant everyone else access, and it never touches a group.
    """

    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username="s", password="p"
        )

    def test_holds_every_permission_with_no_group_membership(self):
        self.assertEqual(self.superuser.groups.count(), 0)
        self.assertTrue(self.superuser.has_perm("app.manage_site"))
        self.assertTrue(self.superuser.has_perm("app.manage_app_users"))

    def test_passes_the_page_guard_and_the_json_guard(self):
        client = client_for(self.superuser)
        self.assertEqual(client.get("/admin/").status_code, 200)
        self.assertEqual(client.get("/api/admin/users/").status_code, 200)


@pytest.mark.postgres
class AdminPageGuardTests(TestCase):
    """The dashboard shell is guarded by login_required + its tab check."""

    def setUp(self):
        self.staff = join(
            User.objects.create_user(username="a", password="p"),
            FLP_STAFF_GROUP,
        )
        self.nobody = User.objects.create_user(username="n", password="p")

    def test_flp_staff_get_the_page(self):
        self.assertEqual(
            client_for(self.staff).get("/admin/").status_code, 200
        )

    def test_user_without_permission_is_forbidden(self):
        self.assertEqual(
            client_for(self.nobody).get("/admin/").status_code, 403
        )

    def test_anonymous_is_redirected_to_login_not_forbidden(self):
        # login_required stays outermost precisely so this is a 302.
        self.assertEqual(client_for().get("/admin/").status_code, 302)


@pytest.mark.postgres
class AdminApiGuardTests(TestCase):
    def setUp(self):
        self.staff = join(
            User.objects.create_user(username="a", password="p"),
            FLP_STAFF_GROUP,
        )
        self.nobody = User.objects.create_user(username="n", password="p")

    def test_manage_site_endpoints_reject_users_without_permission(self):
        for path in ("/api/admin/users/", "/api/admin/site/"):
            with self.subTest(path=path):
                response = client_for(self.nobody).get(path)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["error"], "Forbidden")

    def test_manage_site_endpoints_allow_flp_staff(self):
        for path in ("/api/admin/users/", "/api/admin/site/"):
            with self.subTest(path=path):
                self.assertEqual(
                    client_for(self.staff).get(path).status_code, 200
                )
