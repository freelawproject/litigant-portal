"""Postgres tests: the dev and QA "Start over" control (#969).

Start over returns a session to where it began: the visitor's chats, uploads
and answers go, and nobody else's. Seeded data (topics, flows, variables)
is the baseline and stays. Production has no such endpoint.
"""

import pytest
from django.test import override_settings
from django.urls import reverse

from litigant_portal.app.models import (
    ChatThread,
    UserIdentity,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.models.choices import VariableDataType

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
def test_start_over_ignores_an_offsite_next(client):
    response = client.post(START_OVER, {"next": "https://example.com/"})
    assert response["Location"] == reverse("pages:home")

