"""User admins manage the app users on their instance (#1043).

A user admin holds ``app.manage_app_users`` through the User admins group.
The same role serves an FLP test account on QA and a court's own account on
its pilot; the instance decides whose accounts it covers. The guards are the
security boundary, so the refusals matter more than the happy paths: a user
admin must never reach staff (superusers, Admins, Developers) or the Site
and Topics endpoints.
"""

from unittest import mock

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings

from litigant_portal.app.models import (
    ChatThread,
    UserIdentity,
    UserUpload,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.permissions import USER_ADMINS_GROUP
from litigant_portal.app.services.user import (
    user_admin_toggle,
    user_developer_toggle,
)
from litigant_portal.app.tests.test_permissions import client_for, reload

User = get_user_model()

PASSWORD = "a-long-test-passphrase"
NEW_PASSWORD = "a-brand-new-passphrase"


def user_admin(username: str, email: str) -> User:
    user = User.objects.create_user(
        username=username, email=email, password=PASSWORD
    )
    user.groups.add(Group.objects.get(name=USER_ADMINS_GROUP))
    return reload(user)


def new_password(password: str = NEW_PASSWORD, confirm: str | None = None):
    return {
        "password": password,
        "password_confirm": password if confirm is None else confirm,
    }


def action_paths(user_id: int) -> list[str]:
    return [
        f"/api/admin/users/{user_id}/password/",
        f"/api/admin/users/{user_id}/disable/",
        f"/api/admin/users/{user_id}/enable/",
        f"/api/admin/users/{user_id}/delete/",
        f"/api/admin/users/{user_id}/user-admin/toggle/",
    ]


class UserAdminSetup(TestCase):
    def setUp(self):
        self.user_admin = user_admin("ua", "ua@court.gov")
        self.app_user = User.objects.create_user(
            username="jane", email="jane@example.com", password=PASSWORD
        )
        self.admin = User.objects.create_user(
            username="a", email="a@free.law", password=PASSWORD
        )
        user_admin_toggle(user=self.admin)
        self.admin = reload(self.admin)
        self.developer = User.objects.create_user(
            username="d", email="d@free.law", password=PASSWORD
        )
        user_developer_toggle(user=self.developer)
        self.developer = reload(self.developer)
        self.superuser = User.objects.create_superuser(
            username="s", email="s@free.law", password=PASSWORD
        )
        # Django admin access with no group: staff all the same.
        self.staff = User.objects.create_user(
            username="st",
            email="st@free.law",
            password=PASSWORD,
            is_staff=True,
        )
        self.client = client_for(self.user_admin)

    def emails(self, response) -> list[str]:
        return sorted(u["email"] for u in response.json()["users"])


@pytest.mark.postgres
class UserAdminGroupTests(TestCase):
    def test_user_admins_hold_only_app_user_management(self):
        group = Group.objects.get(name=USER_ADMINS_GROUP)
        self.assertEqual(
            [p.codename for p in group.permissions.all()],
            ["manage_app_users"],
        )


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True)
class UserAdminPageTests(UserAdminSetup):
    def test_user_admin_gets_the_users_tab_only(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["admin_tabs"], ["users"])

    def test_admin_keeps_every_tab(self):
        response = client_for(self.admin).get("/admin/")
        self.assertEqual(
            response.context["admin_tabs"],
            ["settings", "users", "knowledge", "simulate"],
        )

    def test_site_and_topic_endpoints_refuse_user_admins(self):
        for path in ("/api/admin/site/", "/api/admin/topics/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=False)
class UserAdminOffOnProdTests(UserAdminSetup):
    """Plain prod has no user admin, so the role grants nothing."""

    def test_page_refuses_user_admin(self):
        self.assertEqual(self.client.get("/admin/").status_code, 403)

    def test_user_list_refuses_user_admin(self):
        response = self.client.get("/api/admin/users/")
        self.assertEqual(response.status_code, 403)

    def test_actions_are_not_found(self):
        paths = ["/api/admin/users/create/", *action_paths(self.app_user.pk)]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path).status_code, 404)


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="qa", PILOT=False)
class UserAdminOnQaTests(UserAdminSetup):
    def test_user_admin_works_on_qa(self):
        response = self.client.post(
            f"/api/admin/users/{self.app_user.pk}/password/", new_password()
        )
        self.assertEqual(response.status_code, 200)


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True)
class UserListTests(UserAdminSetup):
    def test_user_admin_sees_app_users_but_no_staff(self):
        self.app_user.is_active = False
        self.app_user.save()
        response = self.client.get("/api/admin/users/")
        # Disabled accounts stay listed so they can be enabled again.
        self.assertEqual(
            self.emails(response), ["jane@example.com", "ua@court.gov"]
        )

    def test_admin_still_sees_every_account(self):
        response = client_for(self.admin).get("/api/admin/users/")
        self.assertEqual(
            self.emails(response),
            [
                "a@free.law",
                "d@free.law",
                "jane@example.com",
                "s@free.law",
                "st@free.law",
                "ua@court.gov",
            ],
        )

    def test_rows_say_which_actions_the_viewer_may_take(self):
        rows = {
            u["email"]: u
            for u in self.client.get("/api/admin/users/").json()["users"]
        }
        self.assertTrue(rows["ua@court.gov"]["is_user_admin"])
        self.assertTrue(rows["ua@court.gov"]["can_manage"])
        self.assertFalse(rows["ua@court.gov"]["can_lock_out"])
        self.assertTrue(rows["jane@example.com"]["can_lock_out"])

    def test_admin_rows_for_developers_are_not_manageable(self):
        rows = {
            u["email"]: u
            for u in client_for(self.admin)
            .get("/api/admin/users/")
            .json()["users"]
        }
        self.assertFalse(rows["d@free.law"]["can_manage"])
        self.assertTrue(rows["jane@example.com"]["can_manage"])


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True)
class UserCreateTests(UserAdminSetup):
    def create(self, email="new@example.com", **password):
        data = {"email": email, **new_password(PASSWORD)}
        data.update(password)
        return self.client.post("/api/admin/users/create/", data)

    def test_new_account_is_a_plain_app_user_that_can_log_in(self):
        response = self.create()
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.groups.exists())
        self.assertEqual(
            authenticate(email="new@example.com", password=PASSWORD), user
        )

    def test_mismatched_confirmation_is_refused(self):
        response = self.create(password_confirm="something-else-entirely")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())

    def test_email_is_trimmed_and_lowercased(self):
        self.assertEqual(
            self.create(email="  New@Example.COM ").status_code, 200
        )
        self.assertTrue(User.objects.filter(email="new@example.com").exists())

    def test_email_taken_as_a_username_is_refused(self):
        User.objects.create_user(username="taken@example.com", email="")
        self.assertEqual(
            self.create(email="taken@example.com").status_code, 400
        )

    def test_email_left_on_another_account_by_allauth_is_refused(self):
        # A superuser changed this account's email in Django admin; allauth
        # still holds the old address.
        EmailAddress.objects.create(
            user=self.app_user, email="old@example.com", primary=False
        )
        self.assertEqual(self.create(email="old@example.com").status_code, 400)

    def test_email_too_long_for_a_username_is_refused(self):
        # Valid (no part over its own limit) but 156 characters long, past
        # User.username's 150.
        email = "a" * 60 + "@" + "b" * 60 + "." + "c" * 30 + ".com"
        self.assertEqual(self.create(email=email).status_code, 400)
        self.assertFalse(User.objects.filter(email=email).exists())

    def test_existing_email_is_refused_in_any_case(self):
        self.assertEqual(
            self.create(email="JANE@Example.com").status_code, 400
        )
        self.assertEqual(
            User.objects.filter(email__iexact="jane@example.com").count(), 1
        )

    def test_invalid_email_is_refused(self):
        self.assertEqual(self.create(email="not-an-email").status_code, 400)
        self.assertFalse(User.objects.filter(email="not-an-email").exists())

    def test_password_validators_apply(self):
        response = self.create(password="123", password_confirm="123")
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email="new@example.com").exists())


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True)
class UserActionTests(UserAdminSetup):
    def post(self, action: str, data=None):
        return self.client.post(
            f"/api/admin/users/{self.app_user.pk}/{action}/", data or {}
        )

    def test_password_reset_works_at_login(self):
        self.assertEqual(
            self.post("password", new_password()).status_code, 200
        )
        self.assertEqual(
            authenticate(email="jane@example.com", password=NEW_PASSWORD),
            reload(self.app_user),
        )

    def test_password_reset_needs_a_matching_confirmation(self):
        response = self.post(
            "password", new_password(confirm="something-else-entirely")
        )
        self.assertEqual(response.status_code, 400)
        self.assertTrue(reload(self.app_user).check_password(PASSWORD))

    def test_password_validators_apply_on_reset(self):
        response = self.post("password", new_password("123"))
        self.assertEqual(response.status_code, 400)
        self.assertTrue(reload(self.app_user).check_password(PASSWORD))

    def test_disable_blocks_login_and_enable_restores_it(self):
        self.assertFalse(self.post("disable").json()["is_active"])
        self.assertIsNone(
            authenticate(email="jane@example.com", password=PASSWORD)
        )
        self.assertTrue(self.post("enable").json()["is_active"])
        self.assertEqual(
            authenticate(email="jane@example.com", password=PASSWORD),
            reload(self.app_user),
        )

    def test_delete_removes_the_account_and_what_it_owns(self):
        identity = UserIdentity.objects.create(user=self.app_user)
        variable = Variable.objects.create(
            name="county", data_type=VariableDataType.TEXT
        )
        VariableAnswer.objects.create(
            identity=identity, variable=variable, value="Cass"
        )
        ChatThread.objects.create(identity=identity, thread_type="user_chat")
        file_name = f"uploads/{identity.pk}/ticket.txt"
        UserUpload.objects.create(
            identity=identity,
            file=file_name,
            name="ticket.txt",
            content_type="text/plain",
            size=5,
        )
        storage = UserUpload._meta.get_field("file").storage
        with (
            mock.patch.object(storage, "delete") as storage_delete,
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.assertEqual(self.post("delete").status_code, 200)

        self.assertFalse(User.objects.filter(pk=self.app_user.pk).exists())
        self.assertFalse(UserIdentity.objects.filter(pk=identity.pk).exists())
        self.assertFalse(ChatThread.objects.exists())
        self.assertFalse(VariableAnswer.objects.exists())
        self.assertFalse(UserUpload.objects.exists())
        # The rows cascade on their own; the stored file only goes because
        # the delete runs the identity reset first.
        storage_delete.assert_called_once_with(file_name)

    def test_user_admin_can_make_an_app_user_a_user_admin(self):
        self.assertTrue(self.post("user-admin/toggle").json()["is_user_admin"])
        self.assertTrue(reload(self.app_user).has_perm("app.manage_app_users"))

    def test_user_admin_can_reset_their_own_password_and_stay_signed_in(
        self,
    ):
        response = self.client.post(
            f"/api/admin/users/{self.user_admin.pk}/password/", new_password()
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/admin/users/").status_code, 200)

    def test_user_admin_cannot_lock_themselves_out(self):
        for action in ("disable", "delete", "user-admin/toggle"):
            path = f"/api/admin/users/{self.user_admin.pk}/{action}/"
            with self.subTest(action=action):
                self.assertEqual(self.client.post(path).status_code, 403)
        user_admin = reload(self.user_admin)
        self.assertTrue(user_admin.is_active)
        self.assertTrue(user_admin.has_perm("app.manage_app_users"))


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True)
class UserAdminRefusalTests(UserAdminSetup):
    def test_staff_accounts_are_refused(self):
        staff = (self.admin, self.developer, self.superuser, self.staff)
        for target in staff:
            for path in action_paths(target.pk):
                with self.subTest(target=target.email, path=path):
                    response = self.client.post(path, new_password())
                    self.assertEqual(response.status_code, 403)
        for target in staff:
            target = reload(target)
            self.assertTrue(target.is_active)
            self.assertTrue(target.check_password(PASSWORD))

    def test_unknown_account_is_not_found(self):
        for path in action_paths(999999):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path).status_code, 404)

    def test_app_users_without_the_permission_are_refused(self):
        client = client_for(self.app_user)
        paths = ["/api/admin/users/create/", *action_paths(self.app_user.pk)]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(client.post(path).status_code, 403)

    def test_admin_cannot_act_on_a_developer(self):
        response = client_for(self.admin).post(
            f"/api/admin/users/{self.developer.pk}/password/", new_password()
        )
        self.assertEqual(response.status_code, 403)

    def test_developer_cannot_act_on_a_superuser(self):
        response = client_for(self.developer).post(
            f"/api/admin/users/{self.superuser.pk}/password/", new_password()
        )
        self.assertEqual(response.status_code, 403)

    def test_user_admins_cannot_act_on_each_other(self):
        other = user_admin("ua2", "ua2@court.gov")
        for path in action_paths(other.pk):
            with self.subTest(path=path):
                response = self.client.post(path, new_password())
                self.assertEqual(response.status_code, 403)
        other = reload(other)
        self.assertTrue(other.is_active)
        self.assertTrue(other.check_password(PASSWORD))
        self.assertTrue(other.has_perm("app.manage_app_users"))

    def test_only_a_superuser_acts_on_a_user_admin(self):
        path = f"/api/admin/users/{self.user_admin.pk}/password/"
        for viewer in (self.admin, self.developer):
            with self.subTest(viewer=viewer.email):
                response = client_for(viewer).post(path, new_password())
                self.assertEqual(response.status_code, 403)
        response = client_for(self.superuser).post(path, new_password())
        self.assertEqual(response.status_code, 200)

    def test_adding_a_user_admin_to_admins_does_not_open_them_up(self):
        # A site admin can grant Admins, but that mustn't let them past the
        # superuser-only rule for user admins: every protection applies.
        user_admin_toggle(user=self.user_admin)
        response = client_for(self.admin).post(
            f"/api/admin/users/{self.user_admin.pk}/password/", new_password()
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(reload(self.user_admin).check_password(PASSWORD))

    def test_developer_can_act_on_an_admin(self):
        response = client_for(self.developer).post(
            f"/api/admin/users/{self.admin.pk}/password/", new_password()
        )
        self.assertEqual(response.status_code, 200)
