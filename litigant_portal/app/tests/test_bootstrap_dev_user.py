"""Tests for the bootstrap_dev_user management command."""

from io import StringIO
from unittest import mock

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from litigant_portal.app.services.user import DEVELOPERS_GROUP

User = get_user_model()

EMAIL = "dev@example.com"
PASSWORD = "test-bootstrap-password"


def _run(**env):
    out = StringIO()
    with mock.patch.dict("os.environ", env, clear=False):
        call_command("bootstrap_dev_user", stdout=out)
    return out.getvalue()


@pytest.mark.postgres
class BootstrapDevUserTests(TestCase):
    def test_skips_when_env_unset(self):
        output = _run(DEV_USER_EMAIL="", DEV_USER_PASSWORD="")
        self.assertIn("skipping", output)
        self.assertEqual(User.objects.count(), 0)

    def test_skips_when_only_email_set(self):
        output = _run(DEV_USER_EMAIL=EMAIL, DEV_USER_PASSWORD="")
        self.assertIn("skipping", output)
        self.assertEqual(User.objects.count(), 0)

    def test_creates_dev_user_with_verified_email(self):
        output = _run(DEV_USER_EMAIL=EMAIL, DEV_USER_PASSWORD=PASSWORD)
        self.assertIn("Created dev user", output)

        user = User.objects.get(email=EMAIL)
        self.assertTrue(user.groups.filter(name=DEVELOPERS_GROUP).exists())
        # Developer status is the group, not the Django-admin flags.
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password(PASSWORD))

        address = EmailAddress.objects.get(user=user, email=EMAIL)
        self.assertTrue(address.verified)
        self.assertTrue(address.primary)

    def test_refuses_to_promote_existing_user(self):
        user = User.objects.create_user(
            username=EMAIL, email=EMAIL, password="original-password"
        )
        output = _run(DEV_USER_EMAIL=EMAIL, DEV_USER_PASSWORD=PASSWORD)
        self.assertIn("refusing to promote", output)

        user.refresh_from_db()
        self.assertFalse(user.groups.filter(name=DEVELOPERS_GROUP).exists())
        self.assertTrue(user.check_password("original-password"))
        # And never mark a pre-registered account's email as verified.
        self.assertFalse(EmailAddress.objects.filter(user=user).exists())

    def test_rerun_is_a_noop(self):
        _run(DEV_USER_EMAIL=EMAIL, DEV_USER_PASSWORD=PASSWORD)
        output = _run(DEV_USER_EMAIL=EMAIL, DEV_USER_PASSWORD=PASSWORD)
        self.assertIn("nothing to do", output)
        self.assertEqual(User.objects.filter(email=EMAIL).count(), 1)
        self.assertEqual(EmailAddress.objects.filter(email=EMAIL).count(), 1)

    def test_email_lookup_is_case_insensitive(self):
        User.objects.create_user(
            username=EMAIL, email=EMAIL, password="original-password"
        )
        output = _run(DEV_USER_EMAIL=EMAIL.upper(), DEV_USER_PASSWORD=PASSWORD)
        self.assertIn("refusing to promote", output)
        self.assertEqual(User.objects.count(), 1)
