"""Tests for two-factor sign-in: the code step, recovery codes, and who
may set it up. All postgres-marked."""

import time

import pytest
from allauth.account.models import EmailAddress
from allauth.mfa.recovery_codes.internal.auth import RecoveryCodes
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    generate_totp_secret,
    hotp_value,
)
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.http import urlencode

from litigant_portal.app.models import UserIdentity, Variable, VariableAnswer
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.permissions import Tier
from litigant_portal.app.services.site import site_update
from litigant_portal.app.services.user import user_create

User = get_user_model()

pytestmark = [
    pytest.mark.postgres,
    pytest.mark.django_db,
    pytest.mark.usefixtures("frozen_clock"),
]

LOGIN_URL = "/accounts/login/"
CODE_URL = "/accounts/2fa/authenticate/"
SETUP_URL = "/accounts/2fa/totp/activate/"
CONFIRM_ACCESS_URL = "/accounts/reauthenticate/"
EMAIL = "staff@example.com"
PASSWORD = "a-long-new-passphrase-42"


@pytest.fixture
def court(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        site_update(court_name="Franklin County Municipal Court")


def _two_factor_user(role=Tier.APP_USER):
    """Return an account with two-factor on, its secret and its recovery
    codes."""
    user = user_create(email=EMAIL, password=PASSWORD, role=role)
    secret = generate_totp_secret()
    TOTP.activate(user, secret)
    recovery_codes = RecoveryCodes.activate(user).generate_codes()
    return user, secret, recovery_codes


def _code(secret):
    return format_hotp_value(hotp_value(secret, int(time.time()) // 30))


def _wrong_code(secret):
    return format_hotp_value((int(_code(secret)) + 1) % 10**6)


def _login(client):
    return client.post(LOGIN_URL, {"login": EMAIL, "password": PASSWORD})


def _login_and_confirm_access(client):
    # The setup page asks for the password again, even after a new sign-in.
    _login(client)
    client.post(CONFIRM_ACCESS_URL, {"password": PASSWORD})


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


def test_sign_in_with_two_factor_asks_for_a_code(client):
    _two_factor_user()

    response = _login(client)

    assert response["Location"] == CODE_URL
    assert not _signed_in(client)
    assert client.get(CODE_URL).status_code == 200


def test_a_correct_code_signs_in(client):
    _, secret, _ = _two_factor_user()
    _login(client)

    response = client.post(CODE_URL, {"code": _code(secret)})

    assert response["Location"] == "/"
    assert _signed_in(client)


def test_a_wrong_code_does_not_sign_in(client):
    _, secret, _ = _two_factor_user()
    _login(client)

    response = client.post(CODE_URL, {"code": _wrong_code(secret)})

    assert response.status_code == 200
    assert response.context["form"].errors["code"] == ["Incorrect code."]
    assert not _signed_in(client)


def test_a_recovery_code_signs_in_once(client):
    _, _, recovery_codes = _two_factor_user()
    _login(client)

    first = client.post(CODE_URL, {"code": recovery_codes[0]})

    assert first["Location"] == "/"
    assert _signed_in(client)

    other = type(client)()
    _login(other)
    second = other.post(CODE_URL, {"code": recovery_codes[0]})

    assert second.status_code == 200
    assert not _signed_in(other)


def test_setup_asks_to_confirm_access_after_a_new_sign_in(client):
    user_create(email=EMAIL, password=PASSWORD)
    _login(client)

    response = client.get(SETUP_URL)

    assert response["Location"] == (
        f"{CONFIRM_ACCESS_URL}?{urlencode({'next': SETUP_URL})}"
    )


def test_sign_in_without_two_factor_has_no_code_step(client):
    user_create(email=EMAIL, password=PASSWORD)

    response = _login(client)

    assert response["Location"] == "/"
    assert _signed_in(client)


def test_staff_with_anonymous_work_reach_the_answers_page_after_the_code(
    client,
):
    _, secret, _ = _two_factor_user(role=Tier.COURT_ADMIN)
    _anonymous_answer(client)
    _login(client)

    response = client.post(CODE_URL, {"code": _code(secret)})

    answers = reverse("pages:anonymous_answers")
    assert response["Location"] == f"{answers}?{urlencode({'next': '/'})}"
    assert _signed_in(client)


def test_setup_link_names_the_court(client, court):
    user_create(email=EMAIL, password=PASSWORD)
    _login_and_confirm_access(client)

    page = client.get(SETUP_URL)

    assert page.status_code == 200
    assert (
        "issuer=Franklin%20County%20Municipal%20Court"
        in page.context["totp_url"]
    )


@pytest.mark.parametrize(
    ("allow_unverified", "status_code"),
    [(False, 302), (True, 200)],
    ids=["refused-when-addresses-are-confirmed", "allowed-without-email"],
)
def test_setup_with_an_unconfirmed_address(
    client, settings, allow_unverified, status_code
):
    settings.MFA_ALLOW_UNVERIFIED_EMAIL = allow_unverified
    user = User.objects.create_user(
        username=EMAIL, email=EMAIL, password=PASSWORD
    )
    EmailAddress.objects.create(
        user=user, email=EMAIL, verified=False, primary=True
    )
    _login_and_confirm_access(client)

    response = client.get(SETUP_URL)

    assert response.status_code == status_code
    if not allow_unverified:
        assert response["Location"] == "/accounts/2fa/"
