"""Tests for the rate limits on the Django admin login."""

import pytest
from django.contrib.auth import get_user_model
from django.http import HttpResponse

from litigant_portal.app.views import django_admin

User = get_user_model()

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

LOGIN_URL = "/django-admin/login/"


def _login(client, username, url=LOGIN_URL):
    return client.post(
        url, {"username": username, "password": "wrong-password"}
    )


def test_admin_login_allows_ten_failures_a_minute_per_ip(ratelimited, client):
    for i in range(10):
        assert _login(client, f"user{i}@example.com").status_code == 200

    assert _login(client, "user10@example.com").status_code == 429


def test_admin_login_allows_five_failures_per_account(ratelimited, client):
    for _ in range(5):
        assert _login(client, "admin@example.com").status_code == 200

    assert _login(client, "admin@example.com").status_code == 429


def test_admin_login_account_limit_ignores_case(ratelimited, client):
    for _ in range(5):
        _login(client, "admin@example.com")

    assert _login(client, " ADMIN@example.com").status_code == 429


def test_admin_login_account_limit_ignores_unicode_form(ratelimited, client):
    for _ in range(5):
        _login(client, "admin@example.com")

    assert _login(client, "ａdmin@example.com").status_code == 429


def test_admin_login_counts_only_failures(ratelimited, client):
    User.objects.create_superuser(
        username="admin@example.com",
        email="admin@example.com",
        password="correct-horse-battery",
    )
    for _ in range(10):
        response = client.post(
            LOGIN_URL,
            {
                "username": "admin@example.com",
                "password": "correct-horse-battery",
            },
        )
        assert response.status_code == 302
        client.logout()

    assert _login(client, "admin@example.com").status_code == 200


def test_admin_login_counts_the_attempt_before_authenticating(
    ratelimited, client, monkeypatch
):
    for _ in range(4):
        _login(client, "admin@example.com")
    seen = {}

    def stub_login(request, extra_context=None):
        seen["taken"] = django_admin._consume(request, dry_run=True) is None
        return HttpResponse()

    monkeypatch.setattr(django_admin.admin.site, "login", stub_login)
    _login(client, "admin@example.com")

    assert seen["taken"]


def test_admin_login_account_limit_is_per_account(ratelimited, client):
    for _ in range(5):
        _login(client, "admin@example.com")

    assert _login(client, "other@example.com").status_code == 200


def test_admin_login_limited_page_says_to_wait(ratelimited, client):
    url = f"{LOGIN_URL}?next=/django-admin/"
    for _ in range(5):
        _login(client, "admin@example.com", url)

    response = _login(client, "admin@example.com", url)
    html = response.content.decode()
    assert "<title>Too many login attempts |" in html
    assert "<h1>Too many login attempts</h1>" in html
    assert "Wait a few minutes and try again." in html
    assert f'href="{url}"' in html
