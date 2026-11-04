"""Tests for the rate limits on the Django admin login."""

import pytest

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

LOGIN_URL = "/django-admin/login/"


@pytest.fixture
def ratelimited(settings):
    settings.RATELIMIT_ENABLE = True


def _login(client, username):
    return client.post(
        LOGIN_URL, {"username": username, "password": "wrong-password"}
    )


def test_admin_login_allows_ten_attempts_a_minute_per_ip(ratelimited, client):
    for i in range(10):
        assert _login(client, f"user{i}@example.com").status_code == 200

    assert _login(client, "user10@example.com").status_code == 403


def test_admin_login_allows_five_attempts_per_account(ratelimited, client):
    for _ in range(5):
        assert _login(client, "admin@example.com").status_code == 200

    assert _login(client, "admin@example.com").status_code == 403


def test_admin_login_account_limit_ignores_case(ratelimited, client):
    for _ in range(5):
        _login(client, "admin@example.com")

    assert _login(client, " ADMIN@example.com").status_code == 403


def test_admin_login_account_limit_is_per_account(ratelimited, client):
    for _ in range(5):
        _login(client, "admin@example.com")

    assert _login(client, "other@example.com").status_code == 200
