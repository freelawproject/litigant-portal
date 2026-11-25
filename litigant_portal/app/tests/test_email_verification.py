"""Tests for email verification: the confirmation emails, the "check
your email" page, and the confirm page. All postgres-marked."""

import re
import time
from unittest import mock

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail

from litigant_portal.app.services.site import site_update

User = get_user_model()

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

SIGNUP_URL = "/accounts/signup/"
LOGIN_URL = "/accounts/login/"
SENT_URL = "/accounts/confirm-email/"
EMAIL = "new@example.com"
PASSWORD = "a-long-new-passphrase-42"
DAY = 24 * 60 * 60


@pytest.fixture(autouse=True)
def mandatory(settings):
    settings.ACCOUNT_EMAIL_VERIFICATION = "mandatory"


@pytest.fixture
def court(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        site_update(court_name="Franklin County Municipal Court")


def _signup(client, email=EMAIL):
    return client.post(
        SIGNUP_URL,
        {"email": email, "password1": PASSWORD, "password2": PASSWORD},
    )


def _user(email=EMAIL):
    return User.objects.create_user(
        username=email, email=email, password=PASSWORD
    )


def _confirm_link(message):
    return re.search(r"https?://\S+", message.body).group()


def test_signup_emails_a_confirm_link(client, court):
    response = _signup(client)

    assert response.status_code == 302
    assert response["Location"] == SENT_URL
    [message] = mail.outbox
    assert message.to == [EMAIL]
    assert message.subject == (
        "Confirm your email address for Franklin County Municipal Court"
    )
    assert "Franklin County Municipal Court" in message.body
    assert "/accounts/confirm-email/" in _confirm_link(message)
    assert "7 days" in message.body
    assert "—" not in message.body


def test_signup_lands_on_the_check_your_email_page(client):
    page = client.get(_signup(client)["Location"])

    assert page.status_code == 200
    assert "account/verification_sent.html" in [t.name for t in page.templates]
    assert "Check your email" in page.content.decode()


def test_signup_with_a_taken_address_emails_its_owner(client, court):
    _user()

    response = _signup(client)

    assert response["Location"] == SENT_URL
    assert User.objects.count() == 1
    [message] = mail.outbox
    assert message.to == [EMAIL]
    assert message.subject == (
        "Your account for Franklin County Municipal Court"
    )
    assert "/accounts/password/reset/" in message.body
    assert "—" not in message.body


def test_sign_in_before_confirming_emails_a_new_link(client, court):
    _user()

    response = client.post(LOGIN_URL, {"login": EMAIL, "password": PASSWORD})

    assert response["Location"] == SENT_URL
    [message] = mail.outbox
    assert message.subject == (
        "Confirm your email address for Franklin County Municipal Court"
    )
    assert "/accounts/confirm-email/" in _confirm_link(message)


def test_opening_the_link_asks_before_it_confirms(client):
    _signup(client)

    page = client.get(_confirm_link(mail.outbox[0]))

    html = page.content.decode()
    assert "Confirm your email address" in html
    assert EMAIL in html
    assert re.search(r'<form[^>]+method="post"', html)
    assert not EmailAddress.objects.get(email=EMAIL).verified


def test_confirm_button_marks_the_address_confirmed(client):
    _signup(client)

    client.post(_confirm_link(mail.outbox[0]))

    assert EmailAddress.objects.get(email=EMAIL).verified


def test_used_link_shows_the_link_no_longer_works_page(client):
    _signup(client)
    link = _confirm_link(mail.outbox[0])
    client.post(link)

    html = client.get(link).content.decode()

    assert "This link no longer works" in html
    assert f'href="{LOGIN_URL}"' in html
    assert "<form" not in html


@pytest.mark.parametrize(
    ("days", "works"), [(6, True), (8, False)], ids=["day-6", "day-8"]
)
def test_confirm_link_lasts_seven_days(client, days, works):
    _signup(client)
    later = time.time() + days * DAY

    with mock.patch("django.core.signing.time.time", return_value=later):
        page = client.get(_confirm_link(mail.outbox[0]))

    assert bool(page.context["confirmation"]) is works
