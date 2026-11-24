"""Tests for "Forgot your password?": the login link, the reset email,
and how long its link works. All postgres-marked."""

import re
from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import mail

from litigant_portal.app.services.site import site_update

User = get_user_model()

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

RESET_URL = "/accounts/password/reset/"
NEW_PASSWORD = "a-long-new-passphrase-42"


@pytest.fixture
def tester():
    return User.objects.create_user(
        username="tester@example.com",
        email="tester@example.com",
        password="old-passphrase-for-test",
    )


def _reset_link(message):
    return re.search(r"https?://\S+", message.body).group()


def _link_works(client, link):
    page = client.get(link, follow=True)
    return not page.context.get("token_fail", False)


@pytest.mark.parametrize(
    ("enabled", "shown"), [(True, True), (False, False)], ids=["on", "off"]
)
def test_login_page_links_to_reset_only_when_email_is_on(
    settings, client, enabled, shown
):
    settings.EMAIL_ENABLED = enabled

    html = client.get("/accounts/login/").content.decode()

    assert (f'href="{RESET_URL}"' in html) is shown


def test_reset_emails_a_link_that_opens_the_set_password_page(
    client, tester, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        site_update(court_name="Franklin County Municipal Court")

    response = client.post(RESET_URL, {"email": "tester@example.com"})

    assert response.status_code == 302
    [message] = mail.outbox
    assert message.to == ["tester@example.com"]
    assert message.subject == (
        "Reset your password for Franklin County Municipal Court"
    )
    assert "Franklin County Municipal Court" in message.body
    assert "7 days" in message.body
    assert "—" not in message.body
    assert _link_works(client, _reset_link(message))


def test_reset_link_sets_a_password_the_tester_can_sign_in_with(
    client, tester
):
    client.post(RESET_URL, {"email": "tester@example.com"})
    page = client.get(_reset_link(mail.outbox[0]), follow=True)

    client.post(
        page.redirect_chain[-1][0],
        {"password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
    )

    assert client.login(username="tester@example.com", password=NEW_PASSWORD)


def test_unknown_address_gets_no_email_and_the_same_done_page(client):
    response = client.post(RESET_URL, {"email": "nobody@example.com"})

    assert response.status_code == 302
    assert response["Location"] == "/accounts/password/reset/done/"
    assert mail.outbox == []


def test_disabled_account_gets_no_email(client, tester):
    tester.is_active = False
    tester.save(update_fields=["is_active"])

    client.post(RESET_URL, {"email": "tester@example.com"})

    assert mail.outbox == []


@pytest.mark.parametrize(
    ("days", "works"), [(6, True), (8, False)], ids=["day-6", "day-8"]
)
def test_reset_link_lasts_seven_days(client, tester, monkeypatch, days, works):
    client.post(RESET_URL, {"email": "tester@example.com"})
    later = datetime.now() + timedelta(days=days)
    monkeypatch.setattr(PasswordResetTokenGenerator, "_now", lambda _: later)

    assert _link_works(client, _reset_link(mail.outbox[0])) is works
