"""Postgres tests: the anonymous answers choice page (#1179).

A signed-in visitor whose session still carries the key of the session they
used before signing in is asked whether to keep that session's answers,
chats and uploads or delete them. The page tests place the key in the
session themselves; the login and signup tests go through allauth and let
the middleware carry it.
"""

import re
from unittest import mock

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import resolve_url
from django.urls import reverse
from django.utils.http import urlencode

from litigant_portal.app.models import (
    ChatThread,
    UserIdentity,
    UserUpload,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.session import ANONYMOUS_SESSION_KEY

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

URL = reverse("pages:anonymous_answers")
SESSION_KEY = "before-signing-in"
EMAIL = "u@example.com"
PASSWORD = "a-long-enough-password"


@pytest.fixture
def variable():
    return Variable.objects.create(
        name="county", data_type=VariableDataType.TEXT
    )


@pytest.fixture
def user():
    return get_user_model().objects.create_user(
        username=EMAIL, email=EMAIL, password=PASSWORD
    )


@pytest.fixture
def signed_in(client, user):
    client.force_login(user)
    session = client.session
    session[ANONYMOUS_SESSION_KEY] = SESSION_KEY
    session.save()
    return client


def _choice_page(next_url):
    return f"{URL}?{urlencode({'next': next_url})}"


def _anonymous_visit(client, variable=None):
    """A visit before signing in: a session, its identity row, and an
    answer when ``variable`` is given. The GET lets the middleware record
    the key, as it does on every anonymous page load."""
    session = client.session
    session.save()
    identity = UserIdentity.objects.create(session_key=session.session_key)
    if variable:
        VariableAnswer.objects.create(
            identity=identity, variable=variable, value="Cass"
        )
    client.get(reverse("account_login"))
    return identity


def _upload(identity, name):
    return UserUpload.objects.create(
        identity=identity,
        file=f"uploads/{identity.pk}/{name}",
        name=name,
        content_type="text/plain",
        size=5,
    )


@pytest.fixture
def pending(variable):
    identity = UserIdentity.objects.create(session_key=SESSION_KEY)
    VariableAnswer.objects.create(
        identity=identity, variable=variable, value="Cass"
    )
    ChatThread.objects.create(identity=identity)
    _upload(identity, "notes.txt")
    return identity


@pytest.fixture
def storage_delete():
    storage = UserUpload._meta.get_field("file").storage
    with mock.patch.object(storage, "delete") as delete:
        yield delete


def test_the_page_lists_the_counts_and_both_choices(signed_in, pending):
    ChatThread.objects.create(identity=pending)
    response = signed_in.get(URL)
    assert response.status_code == 200
    html = response.content.decode()
    counts = re.search(r'<ul role="list"[^>]*>(.*?)</ul>', html, re.S).group(1)
    assert re.findall(r"<li>\s*(.*?)\s*</li>", counts, re.S) == [
        "1 answer",
        "2 chats",
        "1 upload",
    ]
    assert re.search(r'<button[^>]+name="choice"[^>]+value="keep"', html)
    assert re.search(r'<button[^>]+name="choice"[^>]+value="discard"', html)


def test_nothing_pending_returns_to_next(signed_in):
    response = signed_in.get(URL, {"next": "/t/a/b/c/"})
    assert response.status_code == 302
    assert response["Location"] == "/t/a/b/c/"


def test_no_pending_key_leaves_identities_without_one_alone(
    client, user, variable
):
    # A blank key must not match identities that never got one.
    stray = UserIdentity.objects.create(session_key="")
    VariableAnswer.objects.create(
        identity=stray, variable=variable, value="Cass"
    )
    client.force_login(user)
    response = client.get(URL, {"next": "/t/a/b/c/"})
    assert response["Location"] == "/t/a/b/c/"
    assert stray.variable_answers.count() == 1


def test_an_offsite_next_returns_to_the_login_redirect(signed_in):
    response = signed_in.get(URL, {"next": "https://example.com/"})
    assert response["Location"] == resolve_url(settings.LOGIN_REDIRECT_URL)


def test_keep_moves_everything_onto_the_account(signed_in, user, pending):
    signed_in.post(URL, {"choice": "keep"})
    identity = UserIdentity.objects.get(user=user)
    assert VariableAnswer.objects.filter(identity=identity).count() == 1
    assert ChatThread.objects.filter(identity=identity).count() == 1
    assert UserUpload.objects.filter(identity=identity).count() == 1
    assert not UserIdentity.objects.filter(pk=pending.pk).exists()


def test_keep_prefers_the_accounts_answer_on_a_conflict(
    signed_in, user, variable, pending
):
    mine = UserIdentity.objects.create(user=user)
    VariableAnswer.objects.create(
        identity=mine, variable=variable, value="Burleigh"
    )
    signed_in.post(URL, {"choice": "keep"})
    answer = VariableAnswer.objects.get(variable=variable)
    assert answer.identity == mine
    assert answer.value == "Burleigh"


def test_discard_deletes_the_anonymous_identity_and_its_files(
    signed_in, pending, storage_delete, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks() as callbacks:
        signed_in.post(URL, {"choice": "discard"})
        storage_delete.assert_not_called()
    assert not UserIdentity.objects.filter(pk=pending.pk).exists()
    assert not VariableAnswer.objects.exists()
    assert not ChatThread.objects.exists()
    for callback in callbacks:
        callback()
    storage_delete.assert_called_once_with(f"uploads/{pending.pk}/notes.txt")


def test_discard_leaves_the_accounts_own_data_alone(
    signed_in, user, variable, pending
):
    mine = UserIdentity.objects.create(user=user)
    VariableAnswer.objects.create(
        identity=mine, variable=variable, value="Burleigh"
    )
    ChatThread.objects.create(identity=mine)
    _upload(mine, "mine.txt")
    signed_in.post(URL, {"choice": "discard"})
    assert list(VariableAnswer.objects.values_list("identity", flat=True)) == [
        mine.pk
    ]
    assert list(ChatThread.objects.values_list("identity", flat=True)) == [
        mine.pk
    ]
    assert list(UserUpload.objects.values_list("identity", flat=True)) == [
        mine.pk
    ]


@pytest.mark.parametrize("choice", ["keep", "discard"])
def test_a_choice_forgets_the_key_and_returns_to_next(
    signed_in, pending, choice
):
    response = signed_in.post(URL, {"choice": choice, "next": "/t/a/b/c/"})
    assert response["Location"] == "/t/a/b/c/"
    assert ANONYMOUS_SESSION_KEY not in signed_in.session


def test_an_unknown_choice_changes_nothing(signed_in, pending):
    assert signed_in.post(URL, {"choice": "maybe"}).status_code == 400
    assert UserIdentity.objects.filter(pk=pending.pk).exists()
    assert ANONYMOUS_SESSION_KEY in signed_in.session


def test_other_methods_are_not_allowed(signed_in, pending):
    assert signed_in.put(URL).status_code == 405


def test_a_visitor_who_is_not_signed_in_is_sent_to_login(client):
    response = client.get(URL)
    assert response.status_code == 302
    assert response["Location"].startswith(reverse("account_login"))


ABOUT = reverse("pages:about")


def test_login_with_pending_answers_sends_the_next_page_to_the_choice(
    client, user, variable
):
    _anonymous_visit(client, variable)
    response = client.post(
        reverse("account_login"), {"login": EMAIL, "password": PASSWORD}
    )
    assert response.status_code == 302
    response = client.get(ABOUT)
    assert response["Location"] == _choice_page(ABOUT)


def test_login_with_nothing_pending_leaves_no_trace(client, user):
    identity = _anonymous_visit(client)
    client.post(
        reverse("account_login"), {"login": EMAIL, "password": PASSWORD}
    )
    assert client.get(ABOUT).status_code == 200
    assert not UserIdentity.objects.filter(pk=identity.pk).exists()
    assert ANONYMOUS_SESSION_KEY not in client.session


def test_signup_with_pending_answers_sends_the_next_page_to_the_choice(
    client, variable
):
    _anonymous_visit(client, variable)
    response = client.post(
        reverse("account_signup"),
        {"email": EMAIL, "password1": PASSWORD, "password2": PASSWORD},
    )
    assert response.status_code == 302
    response = client.get(ABOUT)
    assert response["Location"] == _choice_page(ABOUT)


def test_every_page_load_is_sent_to_the_choice_until_it_is_made(
    signed_in, pending
):
    assert signed_in.get(ABOUT)["Location"] == _choice_page(ABOUT)
    assert signed_in.get(reverse("pages:home"))["Location"] == _choice_page(
        reverse("pages:home")
    )
    signed_in.post(URL, {"choice": "keep"})
    assert signed_in.get(ABOUT).status_code == 200


def test_the_choice_keeps_the_query_of_the_page_it_interrupted(
    signed_in, pending
):
    response = signed_in.get(f"{ABOUT}?tab=help")
    assert response["Location"] == _choice_page(f"{ABOUT}?tab=help")


@pytest.mark.parametrize(
    ("method", "path", "headers"),
    [
        ("get", reverse("assistant:thread_list"), {}),
        ("get", reverse("account_logout"), {}),
        ("get", reverse("pages:briefcase"), {"Sec-Fetch-Dest": "empty"}),
        ("get", reverse("javascript-catalog"), {"Sec-Fetch-Dest": "script"}),
        ("post", ABOUT, {}),
    ],
    ids=["api-get", "logout", "fetch", "script", "post"],
)
def test_the_api_logout_subresources_and_posts_are_not_interrupted(
    signed_in, pending, method, path, headers
):
    response = getattr(signed_in, method)(path, headers=headers)
    assert response.status_code == 200


def test_a_request_that_says_it_is_a_page_load_is_interrupted(
    signed_in, pending
):
    response = signed_in.get(ABOUT, headers={"Sec-Fetch-Dest": "document"})
    assert response["Location"] == _choice_page(ABOUT)
