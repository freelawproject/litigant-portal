"""Account management on the admin Users tab (#1043, tiers from #1135).

Superuser → FLP Staff → Court Admin → App user. Each tier manages the tiers
below it (reset password, disable, enable, delete) and never its own tier,
itself, or anything above. A Court Admin is a court's own account; it sees
the Users tab alone. The guards are the security boundary, so the refusals
matter more than the happy paths.
"""

import re
import smtplib
from unittest import mock

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import authenticate, get_user_model
from django.core import mail
from django.test import TestCase, override_settings

from litigant_portal.app.models import (
    ChatThread,
    UserIdentity,
    UserUpload,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.permissions import COURT_ADMINS_GROUP, FLP_STAFF_GROUP
from litigant_portal.app.services.user import user_create
from litigant_portal.app.tests.test_permissions import client_for, join, reload

User = get_user_model()

PASSWORD = "a-long-test-passphrase"
NEW_PASSWORD = "a-brand-new-passphrase"


def account(username: str, email: str, **extra) -> User:
    return User.objects.create_user(
        username=username, email=email, password=PASSWORD, **extra
    )


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
        f"/api/admin/users/{user_id}/role/",
    ]


# A Court Admin can assign no role, so its reach is the account actions
# without the role change.
def court_admin_action_paths(user_id: int) -> list[str]:
    return action_paths(user_id)[:-1]


class TierSetup(TestCase):
    def setUp(self):
        self.court_admin = join(
            account("ca", "ca@court.gov"), COURT_ADMINS_GROUP
        )
        self.app_user = account("jane", "jane@example.com")
        self.staff = join(account("f", "f@free.law"), FLP_STAFF_GROUP)
        self.superuser = User.objects.create_superuser(
            username="s", email="s@free.law", password=PASSWORD
        )
        # Django admin access with no group: protected all the same.
        self.django_staff = account("st", "st@free.law", is_staff=True)
        self.client = client_for(self.court_admin)

    def emails(self, response) -> list[str]:
        return sorted(u["email"] for u in response.json()["users"])

    def rows(self, viewer) -> dict:
        response = client_for(viewer).get("/api/admin/users/")
        return {u["email"]: u for u in response.json()["users"]}

    def assert_untouched(self, user: User, *, group: str | None = None):
        user = reload(user)
        self.assertTrue(user.is_active)
        self.assertTrue(user.check_password(PASSWORD))
        if group:
            self.assertTrue(user.groups.filter(name=group).exists())


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True)
class AdminPageTests(TierSetup):
    def test_court_admin_gets_the_users_tab_only(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["admin_tabs"], ["users"])

    def test_flp_staff_get_every_tab(self):
        response = client_for(self.staff).get("/admin/")
        self.assertEqual(
            response.context["admin_tabs"],
            ["settings", "users", "knowledge", "simulate"],
        )

    def test_role_choices_are_the_roles_below_the_viewer(self):
        cases = [
            (self.court_admin, ["app_user"]),
            (self.staff, ["court_admin", "app_user"]),
            (self.superuser, ["flp_staff", "court_admin", "app_user"]),
        ]
        for viewer, roles in cases:
            with self.subTest(viewer=viewer.email):
                response = client_for(viewer).get("/admin/")
                self.assertEqual(
                    [value for value, _ in response.context["role_choices"]],
                    roles,
                )

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {
                "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
                "OPTIONS": {"min_length": 12},
            }
        ]
    )
    def test_password_rules_come_from_the_configured_validators(self):
        # The dialogs state the length up front, so it must be the one
        # validate_password enforces on submit, not copy that can drift.
        response = self.client.get("/admin/")
        self.assertEqual(
            response.context["password_rules"],
            "At least 12 characters.",
        )

    def test_password_rules_state_every_configured_validator(self):
        response = self.client.get("/admin/")
        self.assertEqual(
            response.context["password_rules"],
            "At least 15 characters. "
            "Can't be all numbers, a common password, or similar to email.",
        )

    @override_settings(
        AUTH_PASSWORD_VALIDATORS=[
            {"NAME": f"django.contrib.auth.password_validation.{name}"}
            for name in ("CommonPasswordValidator", "NumericPasswordValidator")
        ]
    )
    def test_two_exclusions_read_as_one_or(self):
        response = self.client.get("/admin/")
        self.assertEqual(
            response.context["password_rules"],
            "Can't be all numbers or a common password.",
        )

    @override_settings(AUTH_PASSWORD_VALIDATORS=[])
    def test_no_password_rules_without_validators(self):
        response = self.client.get("/admin/")
        self.assertEqual(response.context["password_rules"], "")

    def test_site_and_topic_endpoints_refuse_court_admins(self):
        for path in ("/api/admin/site/", "/api/admin/topics/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 403)


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=False)
class AccountsOffOnProdTests(TierSetup):
    """Plain prod has no account management, so Court Admin grants nothing."""

    def test_page_refuses_court_admin(self):
        self.assertEqual(self.client.get("/admin/").status_code, 403)

    def test_user_list_refuses_court_admin(self):
        response = self.client.get("/api/admin/users/")
        self.assertEqual(response.status_code, 403)

    def test_actions_are_not_found(self):
        paths = [
            "/api/admin/users/create/",
            *court_admin_action_paths(self.app_user.pk),
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path).status_code, 404)


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=False)
class RolesOnProdTests(TierSetup):
    """Roles are set from the Users tab on every deploy: the ``user_admin``
    feature gates the account actions, not who holds which role."""

    def set_role(self, viewer, target, role):
        return client_for(viewer).post(
            f"/api/admin/users/{target.pk}/role/", {"role": role}
        )

    def test_superuser_makes_flp_staff(self):
        response = self.set_role(self.superuser, self.app_user, "flp_staff")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(reload(self.app_user).is_staff)

    def test_flp_staff_make_court_admins(self):
        response = self.set_role(self.staff, self.app_user, "court_admin")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            reload(self.app_user)
            .groups.filter(name=COURT_ADMINS_GROUP)
            .exists()
        )

    def test_rows_offer_the_role_picker_but_no_account_actions(self):
        row = self.rows(self.staff)["jane@example.com"]
        self.assertTrue(row["can_set_role"])
        self.assertFalse(row["can_manage"])

    def test_court_admin_cannot_set_roles(self):
        response = self.set_role(self.court_admin, self.app_user, "app_user")
        self.assertEqual(response.status_code, 403)


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="qa", PILOT=False, EMAIL_ENABLED=False)
class AccountsOnQaTests(TierSetup):
    def test_court_admin_works_on_qa(self):
        response = self.client.post(
            f"/api/admin/users/{self.app_user.pk}/password/", new_password()
        )
        self.assertEqual(response.status_code, 200)


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True)
class UserListTests(TierSetup):
    def test_court_admin_sees_app_users_and_court_admins_only(self):
        self.app_user.is_active = False
        self.app_user.save()
        response = self.client.get("/api/admin/users/")
        # Disabled accounts stay listed so they can be enabled again.
        self.assertEqual(
            self.emails(response), ["ca@court.gov", "jane@example.com"]
        )

    def test_flp_staff_see_everyone_but_superusers(self):
        response = client_for(self.staff).get("/api/admin/users/")
        self.assertEqual(
            self.emails(response),
            ["ca@court.gov", "f@free.law", "jane@example.com", "st@free.law"],
        )

    def test_superuser_sees_every_account(self):
        response = client_for(self.superuser).get("/api/admin/users/")
        self.assertIn("s@free.law", self.emails(response))

    def test_rows_carry_each_accounts_role(self):
        rows = self.rows(self.superuser)
        self.assertEqual(
            {email: row["role"] for email, row in rows.items()},
            {
                "ca@court.gov": "court_admin",
                "f@free.law": "flp_staff",
                "jane@example.com": "app_user",
                "s@free.law": "superuser",
                "st@free.law": "flp_staff",
            },
        )

    def test_court_admin_rows_manage_app_users_only(self):
        rows = self.rows(self.court_admin)
        self.assertTrue(rows["jane@example.com"]["can_manage"])
        self.assertFalse(rows["ca@court.gov"]["can_manage"])
        # App user is the only role below theirs, so there's no choice.
        self.assertFalse(rows["jane@example.com"]["can_set_role"])

    def test_flp_staff_rows_manage_the_tiers_below(self):
        rows = self.rows(self.staff)
        for email in ("ca@court.gov", "jane@example.com"):
            with self.subTest(email=email):
                self.assertTrue(rows[email]["can_manage"])
                self.assertTrue(rows[email]["can_set_role"])
        for email in ("f@free.law", "st@free.law"):
            with self.subTest(email=email):
                self.assertFalse(rows[email]["can_manage"])
                self.assertFalse(rows[email]["can_set_role"])


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True, EMAIL_ENABLED=False)
class UserCreateTests(TierSetup):
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

    def test_flp_staff_create_a_court_admin(self):
        response = client_for(self.staff).post(
            "/api/admin/users/create/",
            {
                "email": "clerk@court.gov",
                "role": "court_admin",
                **new_password(PASSWORD),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["role"], "court_admin")
        user = User.objects.get(email="clerk@court.gov")
        self.assertTrue(user.has_perm("app.manage_app_users"))
        self.assertFalse(user.is_staff)

    def test_superuser_creates_flp_staff_with_django_admin_access(self):
        response = client_for(self.superuser).post(
            "/api/admin/users/create/",
            {
                "email": "new@free.law",
                "role": "flp_staff",
                **new_password(PASSWORD),
            },
        )
        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="new@free.law")
        self.assertTrue(user.has_perm("app.manage_site"))
        self.assertTrue(user.is_staff)

    def test_no_one_creates_their_own_role_or_above(self):
        cases = [
            (self.court_admin, "court_admin"),
            (self.staff, "flp_staff"),
            (self.staff, "superuser"),
        ]
        for viewer, role in cases:
            with self.subTest(viewer=viewer.email, role=role):
                response = client_for(viewer).post(
                    "/api/admin/users/create/",
                    {
                        "email": "new@example.com",
                        "role": role,
                        **new_password(PASSWORD),
                    },
                )
                self.assertIn(response.status_code, (400, 403))
                self.assertFalse(
                    User.objects.filter(email="new@example.com").exists()
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
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True, EMAIL_ENABLED=False)
class UserActionTests(TierSetup):
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
        # the delete runs through user_identities_delete.
        storage_delete.assert_called_once_with(file_name)


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True)
class RoleSetTests(TierSetup):
    def set_role(self, viewer, target, role):
        return client_for(viewer).post(
            f"/api/admin/users/{target.pk}/role/", {"role": role}
        )

    def test_flp_staff_promote_an_app_user_to_court_admin_and_back(self):
        response = self.set_role(self.staff, self.app_user, "court_admin")
        self.assertEqual(response.json()["role"], "court_admin")
        self.assertTrue(reload(self.app_user).has_perm("app.manage_app_users"))

        response = self.set_role(self.staff, self.app_user, "app_user")
        self.assertEqual(response.json()["role"], "app_user")
        self.assertFalse(reload(self.app_user).groups.exists())

    def test_flp_staff_cannot_promote_to_flp_staff(self):
        response = self.set_role(self.staff, self.app_user, "flp_staff")
        self.assertEqual(response.status_code, 403)
        user = reload(self.app_user)
        self.assertFalse(user.groups.exists())
        self.assertFalse(user.is_staff)

    def test_superuser_promotes_to_flp_staff_and_back(self):
        self.set_role(self.superuser, self.court_admin, "flp_staff")
        user = reload(self.court_admin)
        self.assertEqual(
            list(user.groups.values_list("name", flat=True)), [FLP_STAFF_GROUP]
        )
        self.assertTrue(user.is_staff)

        self.set_role(self.superuser, user, "app_user")
        user = reload(user)
        self.assertFalse(user.groups.exists())
        self.assertFalse(user.is_staff)

    def test_court_admin_cannot_promote(self):
        response = self.set_role(
            self.court_admin, self.app_user, "court_admin"
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(reload(self.app_user).groups.exists())

    def test_court_admin_cannot_change_their_own_role(self):
        response = self.set_role(
            self.court_admin, self.court_admin, "app_user"
        )
        self.assertEqual(response.status_code, 403)
        self.assert_untouched(self.court_admin, group=COURT_ADMINS_GROUP)

    def test_unknown_role_is_refused(self):
        for role in ("", "superuser", "admin"):
            with self.subTest(role=role):
                response = self.set_role(self.superuser, self.app_user, role)
                self.assertIn(response.status_code, (400, 403))
        self.assertFalse(reload(self.app_user).groups.exists())


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True, EMAIL_ENABLED=False)
class TierRefusalTests(TierSetup):
    def assert_refused(self, viewer, target, paths):
        client = client_for(viewer)
        for path in paths:
            with self.subTest(viewer=viewer.email, path=path):
                response = client.post(path, new_password())
                self.assertEqual(response.status_code, 403)

    def test_court_admin_cannot_reach_its_own_tier_or_above(self):
        other = join(account("ca2", "ca2@court.gov"), COURT_ADMINS_GROUP)
        targets = (
            other,
            self.staff,
            self.django_staff,
            self.superuser,
        )
        for target in targets:
            self.assert_refused(
                self.court_admin, target, court_admin_action_paths(target.pk)
            )
            self.assert_untouched(target)

    def test_court_admin_cannot_manage_themselves(self):
        # Their own resets come from FLP Staff.
        self.assert_refused(
            self.court_admin,
            self.court_admin,
            court_admin_action_paths(self.court_admin.pk),
        )
        self.assert_untouched(self.court_admin, group=COURT_ADMINS_GROUP)

    def test_flp_staff_cannot_reach_their_own_tier_or_above(self):
        other = join(account("f2", "f2@free.law"), FLP_STAFF_GROUP)
        for target in (other, self.staff, self.django_staff, self.superuser):
            self.assert_refused(self.staff, target, action_paths(target.pk))
            self.assert_untouched(target)

    def test_flp_staff_manage_a_court_admin(self):
        client = client_for(self.staff)
        path = f"/api/admin/users/{self.court_admin.pk}/"
        response = client.post(path + "password/", new_password())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(client.post(path + "delete/").status_code, 200)
        self.assertFalse(User.objects.filter(pk=self.court_admin.pk).exists())

    def test_a_court_admin_added_to_flp_staff_is_out_of_reach(self):
        target = join(self.court_admin, FLP_STAFF_GROUP)
        self.assert_refused(self.staff, target, action_paths(target.pk))

    def test_superuser_manages_flp_staff(self):
        response = client_for(self.superuser).post(
            f"/api/admin/users/{self.staff.pk}/password/", new_password()
        )
        self.assertEqual(response.status_code, 200)

    def test_unknown_account_is_not_found(self):
        for path in court_admin_action_paths(999999):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path).status_code, 404)

    def test_app_users_without_the_permission_are_refused(self):
        client = client_for(self.app_user)
        paths = ["/api/admin/users/create/", *action_paths(self.app_user.pk)]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(client.post(path).status_code, 403)


@pytest.mark.postgres
@pytest.mark.django_db
def test_allauth_reset_sends_to_an_account_with_no_password(client):
    # Invites are reset emails: this is the allauth behavior they rest on.
    user = User.objects.create_user(
        username="invited@example.com", email="invited@example.com"
    )
    assert not user.has_usable_password()

    client.post("/accounts/password/reset/", {"email": "invited@example.com"})

    [message] = mail.outbox
    assert message.to == ["invited@example.com"]
    assert "/accounts/password/reset/key/" in message.body


def _link(message) -> str:
    return re.search(r"https?://\S+", message.body).group()


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True, EMAIL_ENABLED=True)
class InviteTests(TierSetup):
    def create(self, email="new@example.com", **extra):
        return self.client.post(
            "/api/admin/users/create/", {"email": email, **extra}
        )

    def test_new_account_has_no_password_and_gets_an_invite(self):
        response = self.create()

        self.assertEqual(response.status_code, 200)
        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.has_usable_password())
        [message] = mail.outbox
        self.assertEqual(message.to, ["new@example.com"])
        self.assertTrue(message.subject.startswith("Set up your account"))
        self.assertIn("7 days", message.body)
        self.assertNotIn("\u2014", message.body)

    def test_invite_link_sets_a_password_the_tester_signs_in_with(self):
        self.create()
        page = self.client_class().get(_link(mail.outbox[0]), follow=True)
        self.assertFalse(page.context.get("token_fail", False))

        tester = self.client_class()
        page = tester.get(_link(mail.outbox[0]), follow=True)
        tester.post(
            page.redirect_chain[-1][0],
            {"password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        )

        self.assertTrue(
            authenticate(email="new@example.com", password=NEW_PASSWORD)
        )

    def test_a_password_sent_anyway_is_ignored(self):
        self.create(**new_password())

        user = User.objects.get(email="new@example.com")
        self.assertFalse(user.has_usable_password())

    def test_failed_send_keeps_the_account_and_says_so(self):
        with mock.patch(
            "django.core.mail.backends.locmem.EmailBackend.send_messages",
            side_effect=smtplib.SMTPException("down"),
        ):
            response = self.create()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email="new@example.com").exists())
        self.assertIn("not sent", response.json()["invite_error"])

    def test_forgot_password_on_an_invited_account_sends_the_invite(self):
        self.create()
        mail.outbox.clear()

        self.client_class().post(
            "/accounts/password/reset/", {"email": "new@example.com"}
        )

        [message] = mail.outbox
        self.assertTrue(message.subject.startswith("Set up your account"))

    def test_rows_mark_invited_accounts(self):
        self.create()

        rows = self.rows(self.court_admin)
        self.assertTrue(rows["new@example.com"]["invited"])
        self.assertFalse(rows["jane@example.com"]["invited"])

    def test_rows_render_the_invited_badge(self):
        html = self.client.get("/admin/").content.decode()

        self.assertRegex(
            html,
            r'<span class="[^"]*rounded-full[^"]*bg-yellow-100[^"]*"\s+'
            r'x-show="user.invited">\s*Invited\s*</span>',
        )

    def test_add_dialog_asks_for_no_password(self):
        html = self.client.get("/admin/").content.decode()

        self.assertNotIn('id="user-create-password"', html)
        self.assertIn("We will email them a link to set their password", html)


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True, EMAIL_ENABLED=False)
class NoEmailTests(TierSetup):
    def test_add_dialog_asks_for_a_password(self):
        html = self.client.get("/admin/").content.decode()

        self.assertIn('id="user-create-password"', html)
        self.assertNotIn("We will email them", html)

    def test_new_account_gets_no_email(self):
        self.client.post(
            "/api/admin/users/create/",
            {"email": "new@example.com", **new_password()},
        )

        self.assertEqual(mail.outbox, [])

    def test_rows_offer_set_password(self):
        html = self.client.get("/admin/").content.decode()

        self.assertIn('id="user-password-dialog"', html)
        self.assertNotIn("Send password link", html)

    def test_password_link_is_not_found(self):
        response = self.client.post(
            f"/api/admin/users/{self.app_user.pk}/password-link/"
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(mail.outbox, [])


@pytest.mark.postgres
@override_settings(DEPLOYMENT_ENV="prod", PILOT=True, EMAIL_ENABLED=True)
class PasswordLinkTests(TierSetup):
    def send(self, target, viewer=None):
        client = client_for(viewer) if viewer else self.client
        return client.post(f"/api/admin/users/{target.pk}/password-link/")

    def test_invited_account_gets_the_invite_again(self):
        invited = user_create(email="new@example.com")

        response = self.send(invited)

        self.assertEqual(response.status_code, 200)
        [message] = mail.outbox
        self.assertEqual(message.to, ["new@example.com"])
        self.assertTrue(message.subject.startswith("Set up your account"))

    def test_account_with_a_password_gets_a_reset_link(self):
        response = self.send(self.app_user)

        self.assertEqual(response.status_code, 200)
        [message] = mail.outbox
        self.assertEqual(message.to, ["jane@example.com"])
        self.assertTrue(message.subject.startswith("Reset your password"))
        self.assertTrue(reload(self.app_user).check_password(PASSWORD))
        self.assertEqual(
            response.json()["notice"],
            "Password link sent to jane@example.com",
        )

    def test_disabled_account_is_refused_and_gets_no_email(self):
        self.app_user.is_active = False
        self.app_user.save(update_fields=["is_active"])

        response = self.send(self.app_user)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(mail.outbox, [])

    def test_account_without_an_address_is_refused(self):
        self.app_user.email = ""
        self.app_user.save(update_fields=["email"])

        response = self.send(self.app_user)

        self.assertEqual(response.status_code, 400)
        self.assertIn("no email address", response.json()["error"])
        self.assertEqual(mail.outbox, [])

    def test_failed_send_says_so(self):
        with mock.patch(
            "django.core.mail.backends.locmem.EmailBackend.send_messages",
            side_effect=smtplib.SMTPException("down"),
        ):
            response = self.send(self.app_user)

        self.assertEqual(response.status_code, 502)
        self.assertIn("not sent", response.json()["error"])

    def test_court_admin_cannot_send_above_its_tier_or_to_itself(self):
        other = join(account("ca2", "ca2@court.gov"), COURT_ADMINS_GROUP)
        for target in (other, self.staff, self.superuser, self.court_admin):
            with self.subTest(target=target.email):
                self.assertEqual(self.send(target).status_code, 403)
        self.assertEqual(mail.outbox, [])

    def test_flp_staff_send_for_a_court_admin(self):
        response = self.send(self.court_admin, viewer=self.staff)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_unknown_account_is_not_found(self):
        response = self.client.post("/api/admin/users/999999/password-link/")

        self.assertEqual(response.status_code, 404)

    def test_app_users_are_refused(self):
        response = self.send(self.app_user, viewer=self.app_user)

        self.assertEqual(response.status_code, 403)

    def test_old_password_endpoint_is_not_found(self):
        response = self.client.post(
            f"/api/admin/users/{self.app_user.pk}/password/", new_password()
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(reload(self.app_user).check_password(PASSWORD))

    def test_rows_offer_send_password_link_not_set_password(self):
        html = self.client.get("/admin/").content.decode()

        self.assertIn("Send password link", html)
        self.assertNotIn('id="user-password-dialog"', html)


@pytest.mark.postgres
@pytest.mark.django_db
def test_password_link_allows_thirty_a_minute_per_ip(ratelimited, settings):
    settings.DEPLOYMENT_ENV = "prod"
    settings.PILOT = True
    settings.EMAIL_ENABLED = True
    client = client_for(
        join(account("ca", "ca@court.gov"), COURT_ADMINS_GROUP)
    )
    path = f"/api/admin/users/{account('jane', 'jane@example.com').pk}/"
    path += "password-link/"
    for _ in range(30):
        assert client.post(path).status_code == 200

    assert client.post(path).status_code == 429
