"""Tests for the bootstrap_superuser management command."""

from io import StringIO
from unittest import mock

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

User = get_user_model()

EMAIL = "admin@example.com"
PASSWORD = "test-bootstrap-password"


def _run(**env):
    out = StringIO()
    with mock.patch.dict("os.environ", env, clear=False):
        call_command("bootstrap_superuser", stdout=out)
    return out.getvalue()


@pytest.mark.postgres
class BootstrapSuperuserTests(TestCase):
    def test_skips_when_env_unset(self):
        output = _run(SUPERUSER_EMAIL="", SUPERUSER_PASSWORD="")
        self.assertIn("skipping", output)
        self.assertEqual(User.objects.count(), 0)

    def test_skips_when_only_email_set(self):
        output = _run(SUPERUSER_EMAIL=EMAIL, SUPERUSER_PASSWORD="")
        self.assertIn("skipping", output)
        self.assertEqual(User.objects.count(), 0)

    def test_creates_superuser_with_verified_email(self):
        output = _run(SUPERUSER_EMAIL=EMAIL, SUPERUSER_PASSWORD=PASSWORD)
        self.assertIn("Created superuser", output)

        user = User.objects.get(email=EMAIL)
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password(PASSWORD))

        address = EmailAddress.objects.get(user=user, email=EMAIL)
        self.assertTrue(address.verified)
        self.assertTrue(address.primary)

    def test_promotes_existing_user_without_touching_password(self):
        user = User.objects.create_user(
            username=EMAIL, email=EMAIL, password="original-password"
        )
        output = _run(SUPERUSER_EMAIL=EMAIL, SUPERUSER_PASSWORD=PASSWORD)
        self.assertIn("Promoted existing user", output)

        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("original-password"))

    def test_rerun_is_a_noop(self):
        _run(SUPERUSER_EMAIL=EMAIL, SUPERUSER_PASSWORD=PASSWORD)
        output = _run(SUPERUSER_EMAIL=EMAIL, SUPERUSER_PASSWORD=PASSWORD)
        self.assertIn("nothing to do", output)
        self.assertEqual(User.objects.filter(email=EMAIL).count(), 1)
        self.assertEqual(EmailAddress.objects.filter(email=EMAIL).count(), 1)

    def test_email_lookup_is_case_insensitive(self):
        User.objects.create_user(
            username=EMAIL, email=EMAIL, password="original-password"
        )
        output = _run(
            SUPERUSER_EMAIL=EMAIL.upper(), SUPERUSER_PASSWORD=PASSWORD
        )
        self.assertIn("Promoted existing user", output)
        self.assertEqual(User.objects.count(), 1)
