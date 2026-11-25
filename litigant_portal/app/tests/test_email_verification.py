"""Tests for email verification: the confirmation emails, the "check
your email" page, the confirm page, and who may sign in before
confirming. All postgres-marked."""

import re
import smtplib
import time
from unittest import mock

import pytest
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils.http import urlencode

from litigant_portal.app.models import UserIdentity, Variable, VariableAnswer
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.services.site import site_update
from litigant_portal.app.services.user import user_create

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


def _signup(client, email=EMAIL, **kwargs):
    return client.post(
        SIGNUP_URL,
        {"email": email, "password1": PASSWORD, "password2": PASSWORD},
        **kwargs,
    )


def _user(email=EMAIL):
    return User.objects.create_user(
        username=email, email=email, password=PASSWORD
    )


def _confirm_link(message):
    return re.search(r"https?://\S+", message.body).group()


def _signed_in(client):
    return "_auth_user_id" in client.session


def _anonymous_answer(client):
    session = client.session
    session.save()
    identity = UserIdentity.objects.create(session_key=session.session_key)
    variable = Variable.objects.create(
        name="county", data_type=VariableDataType.TEXT
    )
    VariableAnswer.objects.create(
        identity=identity, variable=variable, value="Cass"
    )
    # The middleware records the key on an anonymous page load.
    client.get(LOGIN_URL)


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


def test_signup_does_not_sign_in(client):
    _signup(client)

    assert not _signed_in(client)


def test_sign_in_is_blocked_before_confirming(client):
    _user()

    client.post(LOGIN_URL, {"login": EMAIL, "password": PASSWORD})

    assert not _signed_in(client)


def test_sign_in_works_after_confirming(client):
    _signup(client)
    client_class = type(client)
    client_class().post(_confirm_link(mail.outbox[0]))

    response = client_class().post(
        LOGIN_URL, {"login": EMAIL, "password": PASSWORD}
    )

    assert response["Location"] == "/"


def test_confirming_in_the_signup_browser_signs_in(client):
    _signup(client)

    response = client.post(_confirm_link(mail.outbox[0]))

    assert response["Location"] == "/"
    assert _signed_in(client)


def test_confirming_in_another_browser_goes_to_sign_in(client):
    _signup(client)
    other = type(client)()

    response = other.post(_confirm_link(mail.outbox[0]))

    assert response["Location"] == LOGIN_URL
    assert not _signed_in(other)
    assert EmailAddress.objects.get(email=EMAIL).verified


def test_confirming_with_pending_answers_goes_to_the_choice(client):
    _anonymous_answer(client)
    _signup(client)

    response = client.post(_confirm_link(mail.outbox[0]))

    choice = reverse("pages:anonymous_answers")
    assert response["Location"] == f"{choice}?{urlencode({'next': '/'})}"


def test_account_an_admin_added_signs_in_without_confirming(client):
    user_create(email=EMAIL, password=PASSWORD)

    response = client.post(LOGIN_URL, {"login": EMAIL, "password": PASSWORD})

    assert response["Location"] == "/"
    assert _signed_in(client)
    assert mail.outbox == []


def _send_fails():
    return mock.patch(
        "django.core.mail.backends.locmem.EmailBackend.send_messages",
        side_effect=smtplib.SMTPException("down"),
    )


@pytest.mark.parametrize("taken", [False, True], ids=["new", "taken"])
def test_failed_send_at_signup_says_so_on_the_sign_in_page(client, taken):
    if taken:
        _user()

    with _send_fails():
        page = _signup(client, follow=True)

    assert page.redirect_chain == [(LOGIN_URL, 302)]
    html = page.content.decode()
    assert "We could not send the email" in html
    assert "Confirmation email sent" not in html
    assert User.objects.filter(email=EMAIL).count() == 1


def test_failed_send_at_sign_in_says_so_on_the_sign_in_page(client):
    _user()

    with _send_fails():
        page = client.post(
            LOGIN_URL, {"login": EMAIL, "password": PASSWORD}, follow=True
        )

    assert page.redirect_chain == [(LOGIN_URL, 302)]
    assert "We could not send the email" in page.content.decode()
    assert not _signed_in(client)
