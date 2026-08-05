"""Tests for the group/permission system that replaced SiteMembership.

Covers the three layers the admin panel's access control rests on: the
groups the post_migrate receiver provisions, the services that grant and
revoke them, and the view guards that read them. The guards are a security
boundary, so the negative cases (no permission -> 403) matter more than
the happy paths.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.test import Client, TestCase

from litigant_portal.app.permissions import ADMINS_GROUP, DEVELOPERS_GROUP
from litigant_portal.app.selectors.user import user_list
from litigant_portal.app.services.user import (
    user_admin_toggle,
    user_developer_toggle,
)

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


@pytest.mark.postgres
class PermissionGroupTests(TestCase):
    """The groups the post_migrate receiver guarantees."""

    def test_both_groups_exist(self):
        self.assertTrue(Group.objects.filter(name=ADMINS_GROUP).exists())
        self.assertTrue(Group.objects.filter(name=DEVELOPERS_GROUP).exists())

    def test_admins_can_manage_site_only(self):
        group = Group.objects.get(name=ADMINS_GROUP)
        self.assertEqual(
            sorted(p.codename for p in group.permissions.all()),
            ["manage_site"],
        )

    def test_developers_are_a_superset_of_admins(self):
        group = Group.objects.get(name=DEVELOPERS_GROUP)
        self.assertEqual(
            sorted(p.codename for p in group.permissions.all()),
            ["manage_developers", "manage_site"],
        )

    def test_permissions_belong_to_the_app_label(self):
        # The guards check "app.manage_site"; a permission created under
        # another content type would never match.
        codenames = Permission.objects.filter(
            content_type__app_label="app",
            codename__in=["manage_site", "manage_developers"],
        ).count()
        self.assertEqual(codenames, 2)


@pytest.mark.postgres
class GroupToggleTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="u", password="p")

    def test_new_user_holds_neither_permission(self):
        self.assertFalse(self.user.has_perm("app.manage_site"))
        self.assertFalse(self.user.has_perm("app.manage_developers"))

    def test_admin_toggle_grants_then_revokes(self):
        self.assertTrue(user_admin_toggle(user=self.user))
        self.assertTrue(reload(self.user).has_perm("app.manage_site"))

        self.assertFalse(user_admin_toggle(user=self.user))
        self.assertFalse(reload(self.user).has_perm("app.manage_site"))

    def test_developer_toggle_grants_both_permissions(self):
        user_developer_toggle(user=self.user)
        user = reload(self.user)
        self.assertTrue(user.has_perm("app.manage_site"))
        self.assertTrue(user.has_perm("app.manage_developers"))

    def test_dropping_admins_keeps_site_access_while_developer(self):
        # Developers carry manage_site in their own right, so revoking the
        # Admins group must not strip it.
        user_admin_toggle(user=self.user)
        user_developer_toggle(user=self.user)
        user_admin_toggle(user=self.user)
        self.assertTrue(reload(self.user).has_perm("app.manage_site"))

    def test_user_list_annotates_group_membership(self):
        user_admin_toggle(user=self.user)
        row = user_list().get(pk=self.user.pk)
        self.assertTrue(row.is_admin_member)
        self.assertFalse(row.is_developer_member)


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

    def test_holds_both_permissions_with_no_group_membership(self):
        self.assertEqual(self.superuser.groups.count(), 0)
        self.assertTrue(self.superuser.has_perm("app.manage_site"))
        self.assertTrue(self.superuser.has_perm("app.manage_developers"))

    def test_passes_the_page_guard_and_both_json_guards(self):
        client = client_for(self.superuser)
        self.assertEqual(client.get("/admin/").status_code, 200)
        self.assertEqual(client.get("/api/admin/users/").status_code, 200)

        target = User.objects.create_user(username="t", password="p")
        response = client.post(
            f"/api/admin/users/{target.pk}/developer/toggle/"
        )
        self.assertEqual(response.status_code, 200)


@pytest.mark.postgres
class AdminPageGuardTests(TestCase):
    """The dashboard shell is guarded by login_required + permission_required."""

    def setUp(self):
        self.admin = User.objects.create_user(username="a", password="p")
        user_admin_toggle(user=self.admin)
        self.admin = reload(self.admin)
        self.nobody = User.objects.create_user(username="n", password="p")

    def test_permitted_user_gets_the_page(self):
        self.assertEqual(
            client_for(self.admin).get("/admin/").status_code, 200
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
        self.admin = User.objects.create_user(username="a", password="p")
        user_admin_toggle(user=self.admin)
        self.admin = reload(self.admin)

        self.developer = User.objects.create_user(username="d", password="p")
        user_developer_toggle(user=self.developer)
        self.developer = reload(self.developer)

        self.nobody = User.objects.create_user(username="n", password="p")

    def test_manage_site_endpoints_reject_users_without_permission(self):
        for path in ("/api/admin/users/", "/api/admin/sites/"):
            with self.subTest(path=path):
                response = client_for(self.nobody).get(path)
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["error"], "Forbidden")

    def test_manage_site_endpoints_allow_admins(self):
        for path in ("/api/admin/users/", "/api/admin/sites/"):
            with self.subTest(path=path):
                self.assertEqual(
                    client_for(self.admin).get(path).status_code, 200
                )

    def test_developer_toggle_requires_manage_developers(self):
        # An Admin holds manage_site but not manage_developers, so they
        # cannot promote anyone to developer.
        target = User.objects.create_user(username="t", password="p")
        path = f"/api/admin/users/{target.pk}/developer/toggle/"

        self.assertEqual(client_for(self.admin).post(path).status_code, 403)
        self.assertEqual(
            client_for(self.developer).post(path).status_code, 200
        )

    def test_admin_toggle_round_trips_and_reports_state(self):
        target = User.objects.create_user(username="t", password="p")
        path = f"/api/admin/users/{target.pk}/admin/toggle/"

        response = client_for(self.admin).post(path)
        self.assertTrue(response.json()["is_admin"])
        self.assertTrue(reload(target).has_perm("app.manage_site"))

        response = client_for(self.admin).post(path)
        self.assertFalse(response.json()["is_admin"])
        self.assertFalse(reload(target).has_perm("app.manage_site"))

    def test_admin_cannot_revoke_their_own_admin_access(self):
        response = client_for(self.admin).post(
            f"/api/admin/users/{self.admin.pk}/admin/toggle/"
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(reload(self.admin).has_perm("app.manage_site"))

    def test_developer_may_change_their_own_admin_access(self):
        # A developer keeps manage_site through the Developers group, so
        # there's nothing to lock themselves out of.
        response = client_for(self.developer).post(
            f"/api/admin/users/{self.developer.pk}/admin/toggle/"
        )
        self.assertEqual(response.status_code, 200)

    def test_developer_cannot_revoke_their_own_developer_status(self):
        response = client_for(self.developer).post(
            f"/api/admin/users/{self.developer.pk}/developer/toggle/"
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            reload(self.developer).has_perm("app.manage_developers")
        )

    def test_user_payload_reports_group_membership_not_effective_access(self):
        # The pills track group membership directly: a Developer is not in
        # the Admins group, so "is_admin" is False even though they hold
        # manage_site through Developers. The toggles grant groups, so this
        # is what makes them round-trip honestly.
        response = client_for(self.developer).get("/api/admin/users/")
        rows = {u["id"]: u for u in response.json()["users"]}

        self.assertFalse(rows[self.developer.pk]["is_admin"])
        self.assertTrue(rows[self.developer.pk]["is_developer"])
        self.assertTrue(rows[self.admin.pk]["is_admin"])
        self.assertFalse(rows[self.admin.pk]["is_developer"])
