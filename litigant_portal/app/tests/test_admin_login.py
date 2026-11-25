"""Tests for the Django admin login: it goes through the normal sign-in,
so the code step and the sign-in rate limits cover it. All
postgres-marked."""

import re
import time

import pytest
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    generate_totp_secret,
    hotp_value,
)
from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.django_db,
    pytest.mark.usefixtures("frozen_clock"),
]

ADMIN_URL = "/django-admin/"
ADMIN_LOGIN_URL = "/django-admin/login/"
SIGN_IN_URL = "/accounts/login/"
CODE_URL = "/accounts/2fa/authenticate/"
EMAIL = "admin@example.com"
PASSWORD = "a-long-new-passphrase-42"


def _superuser():
    return User.objects.create_superuser(
        username=EMAIL, email=EMAIL, password=PASSWORD
    )


def _signed_in(client):
    return "_auth_user_id" in client.session


def test_admin_login_page_sends_to_the_sign_in_page(client):
    response = client.get(f"{ADMIN_LOGIN_URL}?next={ADMIN_URL}")

    assert response.status_code == 302
    assert response["Location"] == f"{SIGN_IN_URL}?next=%2Fdjango-admin%2F"


def test_admin_page_ends_at_the_sign_in_page_when_signed_out(client):
    response = client.get(ADMIN_URL, follow=True)

    assert response.redirect_chain[-1][0] == (
        f"{SIGN_IN_URL}?next=%2Fdjango-admin%2F"
    )
    assert response.status_code == 200


def test_posting_to_the_admin_login_signs_nobody_in(client):
    _superuser()

    response = client.post(
        ADMIN_LOGIN_URL, {"username": EMAIL, "password": PASSWORD}
    )

    assert response.status_code == 302
    assert response["Location"].startswith(SIGN_IN_URL)
    assert not _signed_in(client)


def test_signed_in_staff_cannot_switch_account_at_the_admin_login(client):
    other = "other@example.com"
    User.objects.create_superuser(
        username=other, email=other, password=PASSWORD
    )
    user = _superuser()
    client.force_login(user)

    response = client.post(
        ADMIN_LOGIN_URL, {"username": other, "password": PASSWORD}
    )

    assert response["Location"] == ADMIN_URL
    assert client.session["_auth_user_id"] == str(user.pk)


def test_admin_login_page_sends_signed_in_staff_to_the_admin(client):
    client.force_login(_superuser())

    response = client.get(f"{ADMIN_LOGIN_URL}?next={ADMIN_URL}auth/user/")

    assert response["Location"] == f"{ADMIN_URL}auth/user/"


@pytest.mark.parametrize("url", [ADMIN_URL, ADMIN_LOGIN_URL])
def test_a_signed_in_litigant_is_sent_to_the_home_page(client, url):
    client.force_login(User.objects.create_user(username="litigant"))

    response = client.get(url, follow=True)

    assert response.redirect_chain[-1][0] == "/"
    assert response.status_code == 200


def test_staff_without_two_factor_reach_the_admin_after_sign_in(client):
    _superuser()

    response = client.post(
        f"{SIGN_IN_URL}?next={ADMIN_URL}",
        {"login": EMAIL, "password": PASSWORD},
    )

    assert response["Location"] == ADMIN_URL
    assert client.get(ADMIN_URL).status_code == 200


def test_the_sign_in_form_sends_staff_back_to_the_admin(client):
    _superuser()
    page = client.get(f"{SIGN_IN_URL}?next={ADMIN_URL}").content.decode()
    field = re.search(
        r'<input type="hidden" name="next" value="([^"]*)"', page
    )

    response = client.post(
        SIGN_IN_URL,
        {"login": EMAIL, "password": PASSWORD, "next": field[1]},
    )

    assert response["Location"] == ADMIN_URL


def test_staff_with_two_factor_reach_the_admin_only_after_the_code(client):
    user = _superuser()
    secret = generate_totp_secret()
    TOTP.activate(user, secret)
    RecoveryCodes.activate(user)

    response = client.post(
        f"{SIGN_IN_URL}?next={ADMIN_URL}",
        {"login": EMAIL, "password": PASSWORD},
    )
    assert response["Location"] == CODE_URL
    assert client.get(ADMIN_URL)["Location"].startswith(ADMIN_LOGIN_URL)
    assert not _signed_in(client)

    code = format_hotp_value(hotp_value(secret, int(time.time()) // 30))
    response = client.post(CODE_URL, {"code": code})

    assert response["Location"] == ADMIN_URL
    assert client.get(ADMIN_URL).status_code == 200
