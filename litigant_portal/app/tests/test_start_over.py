"""Postgres tests: the dev and QA "Start over" control (#969).

Start over returns a session to where it began: the visitor's chats, uploads
and answers go, and nobody else's. Seeded data (topics, flows, variables)
is the baseline and stays. Production has no such endpoint.
"""

from unittest import mock

import pytest
from django.test import override_settings
from django.urls import reverse

from litigant_portal.app.models import (
    ChatThread,
    UserIdentity,
    UserUpload,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.services.user import user_identity_reset

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

START_OVER = reverse("pages:start_over")


@pytest.fixture
def variable(db):
    return Variable.objects.create(
        name="county", data_type=VariableDataType.TEXT
    )


def _identity(client):
    session = client.session
    session.save()
    return UserIdentity.objects.create(session_key=session.session_key)


def _session_data(identity, variable):
    VariableAnswer.objects.create(
        identity=identity, variable=variable, value="Cass"
    )
    ChatThread.objects.create(identity=identity, thread_type="user_chat")


@override_settings(DEPLOYMENT_ENV="prod")
@pytest.mark.parametrize("method", ["get", "post"])
def test_production_has_no_start_over(client, variable, method):
    _session_data(_identity(client), variable)
    assert getattr(client, method)(START_OVER).status_code == 404
    assert VariableAnswer.objects.count() == 1
    assert ChatThread.objects.count() == 1


@override_settings(DEPLOYMENT_ENV="dev")
def test_start_over_only_accepts_a_post(client, variable):
    _session_data(_identity(client), variable)
    assert client.get(START_OVER).status_code == 405
    assert VariableAnswer.objects.count() == 1


@pytest.mark.parametrize("env", ["dev", "qa"])
def test_start_over_clears_the_visitors_chats_and_answers(
    client, variable, env
):
    _session_data(_identity(client), variable)
    someone_else = UserIdentity.objects.create(session_key="another-session")
    _session_data(someone_else, variable)

    with override_settings(DEPLOYMENT_ENV=env):
        client.post(START_OVER)

    assert list(VariableAnswer.objects.values_list("identity", flat=True)) == [
        someone_else.pk
    ]
    assert list(ChatThread.objects.values_list("identity", flat=True)) == [
        someone_else.pk
    ]
    # Seeded data is the baseline and stays.
    assert Variable.objects.filter(pk=variable.pk).exists()


@override_settings(DEPLOYMENT_ENV="dev")
def test_start_over_returns_to_the_page_it_came_from(client):
    response = client.post(START_OVER, {"next": "/t/a/b/c/"})
    assert response["Location"] == "/t/a/b/c/"


@override_settings(DEPLOYMENT_ENV="dev")
def test_start_over_drops_the_query_from_next(client):
    # /chat/?q= re-sends its question on load, so returning there with the
    # query would start a new thread right after the reset.
    response = client.post(START_OVER, {"next": "/chat/?q=my+question"})
    assert response["Location"] == "/chat/"


@override_settings(DEPLOYMENT_ENV="dev")
def test_start_over_ignores_an_offsite_next(client):
    response = client.post(START_OVER, {"next": "https://example.com/"})
    assert response["Location"] == reverse("pages:home")


def _upload(identity, name):
    return UserUpload.objects.create(
        identity=identity,
        file=f"uploads/{identity.pk}/{name}",
        name=name,
        content_type="text/plain",
        size=5,
    )


@pytest.fixture
def storage_delete():
    storage = UserUpload._meta.get_field("file").storage
    with mock.patch.object(storage, "delete") as delete:
        yield delete


def test_start_over_deletes_stored_files_only_once_committed(
    storage_delete, django_capture_on_commit_callbacks
):
    identity = UserIdentity.objects.create(session_key="a-session")
    _upload(identity, "notes.txt")

    with django_capture_on_commit_callbacks() as callbacks:
        user_identity_reset(identity=identity)
        storage_delete.assert_not_called()

    for callback in callbacks:
        callback()
    storage_delete.assert_called_once_with(f"uploads/{identity.pk}/notes.txt")


def test_a_failed_file_delete_still_clears_the_rest(
    storage_delete, django_capture_on_commit_callbacks, caplog
):
    identity = UserIdentity.objects.create(session_key="a-session")
    _upload(identity, "a.txt")
    _upload(identity, "b.txt")
    storage_delete.side_effect = [OSError("storage down"), None]

    with django_capture_on_commit_callbacks(execute=True):
        user_identity_reset(identity=identity)

    assert not UserUpload.objects.filter(identity=identity).exists()
    assert storage_delete.call_count == 2
    assert [r.levelname for r in caplog.records] == ["ERROR"]
