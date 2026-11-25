"""Tests for two-factor sign-in: the code step, recovery codes, who may
set it up, how secrets are stored, the pages, the menu link, the rule
that staff must set it up, and the block for other accounts. All
postgres-marked."""

import logging
import re
import time

import pytest
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
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
from litigant_portal.app.services.user import (
    user_create,
    user_role_set,
    user_two_factor_reset,
)

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
CONFIRM_BY_CODE_URL = "/accounts/2fa/reauthenticate/"
OVERVIEW_URL = "/accounts/2fa/"
TURN_OFF_URL = "/accounts/2fa/totp/deactivate/"
NEW_CODES_URL = "/accounts/2fa/recovery-codes/generate/"
EMAIL = "staff@example.com"
PASSWORD = "a-long-new-passphrase-42"


@pytest.fixture
def court(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        site_update(court_name="Franklin County Municipal Court")


def _two_factor_user(role=Tier.COURT_ADMIN):
    """Return an account with two-factor on, its secret and its recovery
    codes."""
    user = user_create(email=EMAIL, password=PASSWORD, role=role)
    secret = generate_totp_secret()
    TOTP.activate(user, secret)
    recovery_codes = RecoveryCodes.activate(user).generate_codes()
    return user, secret, recovery_codes


def _staff_user():
    return user_create(email=EMAIL, password=PASSWORD, role=Tier.COURT_ADMIN)


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
    _staff_user()
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
    _, secret, _ = _two_factor_user()
    _anonymous_answer(client)
    _login(client)

    response = client.post(CODE_URL, {"code": _code(secret)})

    answers = reverse("pages:anonymous_answers")
    assert response["Location"] == f"{answers}?{urlencode({'next': '/'})}"
    assert _signed_in(client)


def test_setup_link_names_the_court(client, court):
    _staff_user()
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
        username=EMAIL, email=EMAIL, password=PASSWORD, is_staff=True
    )
    EmailAddress.objects.create(
        user=user, email=EMAIL, verified=False, primary=True
    )
    _login_and_confirm_access(client)

    response = client.get(SETUP_URL)

    assert response.status_code == status_code
    if not allow_unverified:
        assert response["Location"] == "/accounts/2fa/"


def test_secrets_are_not_stored_as_plain_text():
    user, secret, _ = _two_factor_user()

    rows = {
        row.type: row.data for row in Authenticator.objects.filter(user=user)
    }

    assert secret not in rows["totp"]["secret"]
    # A plain seed is 80 hex characters.
    assert not re.fullmatch(r"[0-9a-f]{80}", rows["recovery_codes"]["seed"])


def test_an_old_key_in_the_fallbacks_still_reads_the_secret(client, settings):
    _, secret, _ = _two_factor_user()
    settings.TWO_FACTOR_KEY_FALLBACKS = [settings.TWO_FACTOR_KEY]
    settings.TWO_FACTOR_KEY = "a-new-key"
    _login(client)

    response = client.post(CODE_URL, {"code": _code(secret)})

    assert response["Location"] == "/"
    assert _signed_in(client)


@pytest.mark.parametrize(
    "code_from",
    [lambda secret, codes: _code(secret), lambda secret, codes: codes[0]],
    ids=["authenticator-code", "recovery-code"],
)
def test_a_new_key_without_a_fallback_makes_the_code_wrong(
    client, settings, caplog, code_from
):
    _, secret, recovery_codes = _two_factor_user()
    settings.TWO_FACTOR_KEY = "a-new-key"
    _login(client)

    with caplog.at_level(logging.ERROR, logger="litigant_portal.app.adapters"):
        response = client.post(
            CODE_URL, {"code": code_from(secret, recovery_codes)}
        )

    assert response.status_code == 200
    assert response.context["form"].errors["code"] == ["Incorrect code."]
    assert not _signed_in(client)
    assert "Could not decrypt a two-factor secret" in caplog.text


def test_a_new_secret_key_leaves_two_factor_working(client, settings):
    _, secret, _ = _two_factor_user()
    settings.SECRET_KEY = "a-new-key"
    _login(client)

    response = client.post(CODE_URL, {"code": _code(secret)})

    assert response["Location"] == "/"
    assert _signed_in(client)


def _templates(page):
    return [template.name for template in page.templates]


def _input(page, name):
    [tag] = re.findall(
        rf'<input[^>]*name="{name}"[^>]*>', page.content.decode()
    )
    return tag


def test_code_page_uses_our_layout(client):
    _two_factor_user()
    _login(client)

    page = client.get(CODE_URL)

    assert "account/base.html" in _templates(page)
    code = _input(page, "code")
    assert 'autocomplete="one-time-code"' in code
    assert 'inputmode="numeric"' in code
    assert 'form="cancel-sign-in"' in page.content.decode()


def test_code_page_shows_an_error_for_a_wrong_code(client):
    _, secret, _ = _two_factor_user()
    _login(client)

    page = client.post(CODE_URL, {"code": _wrong_code(secret)})

    assert 'aria-invalid="true"' in _input(page, "code")
    assert re.search(
        r'<p id="id_code-error"[^>]*>Incorrect code\.</p>',
        page.content.decode(),
    )


def test_cancel_on_the_code_page_goes_back_to_sign_in(client):
    _two_factor_user()
    _login(client)

    response = client.post("/accounts/logout/", {"next": LOGIN_URL})

    assert response["Location"] == LOGIN_URL
    assert client.get(CODE_URL)["Location"] == LOGIN_URL


def test_confirm_access_page_uses_our_layout(client):
    _staff_user()
    _login(client)

    page = client.get(CONFIRM_ACCESS_URL, {"next": SETUP_URL})

    assert "account/base.html" in _templates(page)
    assert 'autocomplete="current-password"' in _input(page, "password")
    assert f'name="next" value="{SETUP_URL}"' in page.content.decode()


def test_setup_page_shows_the_qr_code_the_key_and_the_code_field(client):
    _staff_user()
    _login_and_confirm_access(client)

    page = client.get(SETUP_URL)

    html = page.content.decode()
    assert "account/base.html" in _templates(page)
    assert re.search(r'<img src="data:image/svg\+xml;base64,[^"]+"', html)
    secret = page.context["form"].secret
    assert re.search(rf'<code id="totp-secret"[^>]*>{secret}</code>', html)
    assert 'inputmode="numeric"' in _input(page, "code")


def test_a_correct_code_at_setup_shows_ten_recovery_codes(client):
    user = _staff_user()
    _login_and_confirm_access(client)
    secret = client.get(SETUP_URL).context["form"].secret

    response = client.post(SETUP_URL, {"code": _code(secret)}, follow=True)

    assert response.redirect_chain == [("/accounts/2fa/recovery-codes/", 302)]
    assert Authenticator.objects.filter(user=user, type="totp").exists()
    assert "account/base.html" in _templates(response)
    html = response.content.decode()
    codes = re.findall(r"<code[^>]*>(\d{8})</code>", html)
    assert len(set(codes)) == 10
    assert 'href="/accounts/2fa/recovery-codes/download/"' in html


def _login_with_code(client, secret):
    _login(client)
    client.post(CODE_URL, {"code": _code(secret)})


def _status(page):
    [text] = re.findall(
        r'<p id="two-factor-status"[^>]*>([^<]*)</p>', page.content.decode()
    )
    return text


def test_overview_shows_that_two_factor_is_off(client):
    _staff_user()
    _login(client)

    page = client.get(OVERVIEW_URL)

    assert "account/base.html" in _templates(page)
    assert _status(page).startswith("Two-factor sign-in is off.")
    assert f'href="{SETUP_URL}"' in page.content.decode()


def test_overview_shows_that_two_factor_is_on(client):
    _, secret, recovery_codes = _two_factor_user()
    _login(client)
    client.post(CODE_URL, {"code": recovery_codes[0]})

    page = client.get(OVERVIEW_URL)

    html = page.content.decode()
    assert _status(page).startswith("Two-factor sign-in is on.")
    assert "9 of 10 recovery codes are left." in html
    assert f'href="{TURN_OFF_URL}"' in html
    assert f'href="{NEW_CODES_URL}"' in html
    assert f'href="{SETUP_URL}"' not in html


@pytest.mark.parametrize("url", [TURN_OFF_URL, NEW_CODES_URL])
def test_manage_pages_ask_to_confirm_access_first(client, url):
    _, secret, _ = _two_factor_user()
    _login_with_code(client, secret)

    response = client.get(url)

    assert response["Location"] == (
        f"{CONFIRM_ACCESS_URL}?{urlencode({'next': url})}"
    )


def test_confirm_access_page_offers_the_code_instead(client):
    _, secret, _ = _two_factor_user()
    _login_with_code(client, secret)

    page = client.get(CONFIRM_ACCESS_URL, {"next": TURN_OFF_URL})

    assert f'href="{CONFIRM_BY_CODE_URL}?' in page.content.decode()


def test_a_code_confirms_access(client):
    _, secret, recovery_codes = _two_factor_user()
    _login_with_code(client, secret)

    page = client.get(CONFIRM_BY_CODE_URL, {"next": TURN_OFF_URL})
    response = client.post(
        CONFIRM_BY_CODE_URL, {"code": recovery_codes[0], "next": TURN_OFF_URL}
    )

    assert "account/base.html" in _templates(page)
    assert 'inputmode="numeric"' in _input(page, "code")
    assert response["Location"] == TURN_OFF_URL
    assert client.get(TURN_OFF_URL).status_code == 200


def test_access_is_confirmed_again_after_five_minutes(client, monkeypatch):
    _, secret, _ = _two_factor_user()
    _login_with_code(client, secret)
    client.post(CONFIRM_ACCESS_URL, {"password": PASSWORD})
    assert client.get(TURN_OFF_URL).status_code == 200

    later = time.time() + 301
    monkeypatch.setattr(
        "allauth.account.internal.flows.reauthentication.time.time",
        lambda: later,
    )

    assert client.get(TURN_OFF_URL).status_code == 302


def test_turning_off_removes_the_authenticator_and_the_recovery_codes(client):
    user, secret, _ = _two_factor_user()
    _login_with_code(client, secret)
    client.post(CONFIRM_ACCESS_URL, {"password": PASSWORD})

    page = client.get(TURN_OFF_URL)
    response = client.post(TURN_OFF_URL)

    assert "account/base.html" in _templates(page)
    assert response["Location"] == OVERVIEW_URL
    assert not Authenticator.objects.filter(user=user).exists()


def test_new_recovery_codes_replace_the_old_ones(client):
    user, secret, old_codes = _two_factor_user()
    _login_with_code(client, secret)
    client.post(CONFIRM_ACCESS_URL, {"password": PASSWORD})

    page = client.get(NEW_CODES_URL)
    response = client.post(NEW_CODES_URL)

    assert "account/base.html" in _templates(page)
    assert "Your old codes stop working." in page.content.decode()
    assert response["Location"] == "/accounts/2fa/recovery-codes/"
    recovery = Authenticator.objects.get(user=user, type="recovery_codes")
    new_codes = recovery.wrap().get_unused_codes()
    assert len(new_codes) == 10
    assert not set(new_codes) & set(old_codes)


@pytest.mark.parametrize(
    ("role", "shown"),
    [(Tier.COURT_ADMIN, True), (Tier.APP_USER, False)],
    ids=["staff", "litigant"],
)
def test_menu_links_to_two_factor_only_for_staff(client, role, shown):
    user_create(email=EMAIL, password=PASSWORD, role=role)
    _login(client)

    page = client.get("/")

    link = re.search(
        rf'<a href="{OVERVIEW_URL}"[^>]*role="menuitem"', page.content.decode()
    )
    assert bool(link) is shown


ADMIN_URL = "/admin/"
ADMIN_API_URL = "/api/admin/site/"


@pytest.fixture
def required(settings):
    settings.STAFF_TWO_FACTOR_REQUIRED = True


def _court_admin():
    return user_create(email=EMAIL, role=Tier.COURT_ADMIN)


def _flp_staff():
    return user_create(email=EMAIL, role=Tier.FLP_STAFF)


def _superuser():
    return User.objects.create_superuser(username=EMAIL, email=EMAIL)


def _django_admin_staff():
    return User.objects.create_user(username=EMAIL, email=EMAIL, is_staff=True)


STAFF = pytest.mark.parametrize(
    "make_user",
    [_court_admin, _flp_staff, _superuser, _django_admin_staff],
    ids=["court-admin", "flp-staff", "superuser", "django-admin-staff"],
)


@STAFF
def test_staff_without_two_factor_are_sent_to_setup(
    client, required, make_user
):
    client.force_login(make_user())

    for url in (ADMIN_URL, "/", "/chat/", OVERVIEW_URL):
        assert client.get(url)["Location"] == SETUP_URL


@STAFF
def test_api_answers_403_to_staff_without_two_factor(
    client, required, make_user
):
    client.force_login(make_user())

    response = client.get(ADMIN_API_URL)

    assert response.status_code == 403
    assert response.json() == {"error": "Set up two-factor sign-in first."}


def test_staff_without_two_factor_can_set_up_and_sign_out(client, required):
    user_create(email=EMAIL, password=PASSWORD, role=Tier.COURT_ADMIN)
    _login(client)

    assert client.get(CONFIRM_ACCESS_URL).status_code == 200
    client.post(CONFIRM_ACCESS_URL, {"password": PASSWORD})
    assert client.get(SETUP_URL).status_code == 200
    assert client.get("/api/health/").status_code == 200
    assert client.post("/accounts/logout/")["Location"] == "/"
    assert not _signed_in(client)


def test_admin_opens_after_setup(client, required):
    user_create(email=EMAIL, password=PASSWORD, role=Tier.FLP_STAFF)
    _login_and_confirm_access(client)
    secret = client.get(SETUP_URL).context["form"].secret

    client.post(SETUP_URL, {"code": _code(secret)})

    assert client.get(ADMIN_URL).status_code == 200
    assert client.get(ADMIN_API_URL).status_code == 200


def test_a_litigant_is_never_sent_to_setup(client, required):
    user_create(email=EMAIL, password=PASSWORD)

    response = _login(client)

    assert response["Location"] == "/"
    assert client.get("/").status_code == 200
    assert client.get("/chat/").status_code == 200


def test_a_litigant_made_court_admin_is_sent_to_setup_on_the_next_page(
    client, required
):
    user = user_create(email=EMAIL, password=PASSWORD)
    _login(client)
    assert client.get("/").status_code == 200

    user_role_set(user=user, role=Tier.COURT_ADMIN)

    assert client.get("/")["Location"] == SETUP_URL


@STAFF
def test_nobody_is_sent_to_setup_when_the_rule_is_off(
    client, settings, make_user
):
    settings.STAFF_TWO_FACTOR_REQUIRED = False
    client.force_login(make_user())

    assert client.get("/").status_code == 200


@pytest.mark.parametrize(
    "url",
    [
        OVERVIEW_URL,
        SETUP_URL,
        TURN_OFF_URL,
        NEW_CODES_URL,
        "/accounts/2fa/recovery-codes/",
        CONFIRM_BY_CODE_URL,
    ],
)
@pytest.mark.parametrize("rule", [True, False], ids=["rule-on", "rule-off"])
def test_two_factor_pages_answer_404_to_a_litigant(
    client, settings, rule, url
):
    settings.STAFF_TWO_FACTOR_REQUIRED = rule
    user_create(email=EMAIL, password=PASSWORD)
    _login(client)

    assert client.get(url).status_code == 404


def test_a_litigant_with_two_factor_still_signs_in_with_the_code(client):
    _, secret, _ = _two_factor_user(role=Tier.APP_USER)

    response = _login(client)
    assert response["Location"] == CODE_URL
    assert client.get(CODE_URL).status_code == 200

    client.post(CODE_URL, {"code": _code(secret)})
    assert _signed_in(client)


def test_a_litigant_with_two_factor_can_turn_it_off(client):
    user, secret, _ = _two_factor_user(role=Tier.APP_USER)
    _login_with_code(client, secret)

    assert client.get(OVERVIEW_URL).status_code == 200
    client.post(CONFIRM_ACCESS_URL, {"password": PASSWORD})
    client.post(TURN_OFF_URL)

    assert not Authenticator.objects.filter(user=user).exists()
    assert client.get(OVERVIEW_URL).status_code == 404


def test_reset_removes_the_authenticator_and_the_recovery_codes(client):
    user, _, _ = _two_factor_user()

    user_two_factor_reset(user=user)

    assert not Authenticator.objects.filter(user=user).exists()
    assert _login(client)["Location"] == "/"
    assert _signed_in(client)


def test_reset_leaves_other_accounts_alone():
    user, _, _ = _two_factor_user()
    other = user_create(email="other@example.com", role=Tier.COURT_ADMIN)

    user_two_factor_reset(user=other)

    assert Authenticator.objects.filter(user=user).count() == 2


@pytest.mark.parametrize(
    ("role", "kept"),
    [(Tier.APP_USER, False), (Tier.COURT_ADMIN, True)],
    ids=["made-app-user", "made-court-admin"],
)
def test_only_a_change_to_app_user_removes_two_factor(role, kept):
    user, _, _ = _two_factor_user(role=Tier.FLP_STAFF)

    user_role_set(user=user, role=role)

    assert Authenticator.objects.filter(user=user).exists() is kept
