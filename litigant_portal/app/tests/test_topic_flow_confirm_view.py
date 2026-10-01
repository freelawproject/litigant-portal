"""The human confirmation endpoint: POST /facts/confirm/ -> reviewed=True.

Only a person, through this session-authenticated page endpoint, may mark
an answer reviewed; no agent tool can (see test_assistant_tools_cannot_confirm).
The routing tests are DB-free; the rest need postgres because they read and
write VariableAnswer rows.
"""

import pytest
from django.test import Client
from django.urls import resolve, reverse
from django.utils import timezone

from litigant_portal.app.models import UserIdentity, Variable, VariableAnswer
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.services.topic_flow import variable_answer_set
from litigant_portal.app.views import topic_flow as topic_flow_views

URL = "/facts/confirm/"


@pytest.fixture
def variables(db):
    Variable.objects.create(name="first_name", data_type=VariableDataType.TEXT)
    Variable.objects.create(name="county", data_type=VariableDataType.TEXT)
    Variable.objects.create(
        name="old_field", data_type=VariableDataType.TEXT, in_schema=False
    )


def _identity(client):
    identity, _ = UserIdentity.objects.get_or_create(
        user=None, session_key=client.session.session_key
    )
    return identity


def _store(client, name, value, reviewed=False):
    variable_answer_set(
        identity=_identity(client),
        variable=Variable.objects.get(name=name),
        value=value,
        reviewed=reviewed,
    )


def _reviewed(client, name):
    return VariableAnswer.objects.get(
        identity=_identity(client), variable__name=name
    ).reviewed


def _session_client(**kwargs):
    client = Client(**kwargs)
    client.session.save()
    return client


def _post(client, names, as_of=None):
    # As the card posts: the names plus when it read them.
    as_of = (as_of or timezone.now()).isoformat()
    return client.post(URL, {"names": names, "as_of": as_of})


# --- routing (DB-free) ------------------------------------------------------


def test_confirm_url_resolves_to_the_confirm_view():
    assert resolve(URL).func is topic_flow_views.topic_flow_confirm


def test_confirm_url_is_a_page_route_not_an_agent_route():
    assert reverse("pages:topic_flow_confirm") == URL


# --- behavior (needs DB) ----------------------------------------------------


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_visitor_confirms_their_own_answers(variables):
    client = _session_client()
    _store(client, "first_name", "Sandra")
    _store(client, "county", "Cass")
    response = _post(client, ["first_name", "county"])
    assert response.status_code == 200
    assert response.json() == {"confirmed": 2, "pending": []}
    assert _reviewed(client, "first_name") is True
    assert _reviewed(client, "county") is True


@pytest.mark.postgres
@pytest.mark.django_db
def test_only_the_named_answers_are_confirmed(variables):
    client = _session_client()
    _store(client, "first_name", "Sandra")
    _store(client, "county", "Cass")
    _post(client, ["county"])
    assert _reviewed(client, "first_name") is False
    assert _reviewed(client, "county") is True


@pytest.mark.postgres
@pytest.mark.django_db
def test_an_answer_changed_after_the_card_was_shown_is_not_confirmed(
    variables,
):
    # The card showed "Cass"; the assistant then re-saved "Burleigh". The
    # click confirms what the person saw, never the newer value.
    client = _session_client()
    _store(client, "first_name", "Sandra")
    _store(client, "county", "Cass")
    shown_at = timezone.now()
    _store(client, "county", "Burleigh")
    response = _post(client, ["first_name", "county"], as_of=shown_at)
    assert response.json() == {"confirmed": 1, "pending": ["county"]}
    assert _reviewed(client, "first_name") is True
    assert _reviewed(client, "county") is False


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_visitor_without_a_session_is_forbidden_and_mints_no_identity(
    variables,
):
    response = _post(Client(), ["county"])
    assert response.status_code == 403
    assert UserIdentity.objects.count() == 0


@pytest.mark.postgres
@pytest.mark.django_db
@pytest.mark.parametrize(
    "names",
    [None, [], ""],
    ids=["no-names", "empty-list", "blank-name"],
)
def test_a_body_without_names_is_rejected_and_writes_nothing(variables, names):
    client = _session_client()
    _store(client, "county", "Cass")
    body = {"as_of": timezone.now().isoformat()}
    if names is not None:
        body["names"] = names
    response = client.post(URL, body)
    assert response.status_code == 400
    assert _reviewed(client, "county") is False


@pytest.mark.postgres
@pytest.mark.django_db
@pytest.mark.parametrize(
    "as_of",
    [None, "", "yesterday", "2026-09-29T12:00:00"],
    ids=["missing", "blank", "not-a-date", "naive"],
)
def test_a_body_without_a_usable_as_of_is_rejected_and_writes_nothing(
    variables, as_of
):
    client = _session_client()
    _store(client, "county", "Cass")
    body = {"names": ["county"]}
    if as_of is not None:
        body["as_of"] = as_of
    response = client.post(URL, body)
    assert response.status_code == 400
    assert _reviewed(client, "county") is False


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_json_body_is_treated_as_having_no_names(variables):
    client = _session_client()
    _store(client, "county", "Cass")
    response = client.post(
        URL, '{"names": ["county"]}', content_type="application/json"
    )
    assert response.status_code == 400
    assert _reviewed(client, "county") is False


@pytest.mark.postgres
@pytest.mark.django_db
def test_an_unanswered_name_confirms_nothing_without_error(variables):
    client = _session_client()
    response = _post(client, ["county", "no_such_variable"])
    assert response.status_code == 200
    assert response.json() == {"confirmed": 0, "pending": []}


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_cleared_answer_cannot_be_confirmed(variables):
    client = _session_client()
    _store(client, "county", "Cass")
    _store(client, "county", None)
    assert _post(client, ["county"]).json() == {"confirmed": 0, "pending": []}
    assert _reviewed(client, "county") is False


@pytest.mark.postgres
@pytest.mark.django_db
def test_an_out_of_schema_answer_cannot_be_confirmed(variables):
    client = _session_client()
    _store(client, "old_field", "kept for migration")
    assert _post(client, ["old_field"]).json() == {
        "confirmed": 0,
        "pending": [],
    }
    assert _reviewed(client, "old_field") is False


@pytest.mark.postgres
@pytest.mark.django_db
def test_another_visitors_answers_are_untouched(variables):
    other = _session_client()
    _store(other, "county", "Burleigh")
    client = _session_client()
    _store(client, "county", "Cass")
    assert _post(client, ["county"]).json() == {"confirmed": 1, "pending": []}
    assert _reviewed(other, "county") is False


@pytest.mark.postgres
@pytest.mark.django_db
def test_confirming_twice_is_idempotent(variables):
    client = _session_client()
    _store(client, "county", "Cass")
    _post(client, ["county"])
    # Zero confirmed but nothing pending: the card treats this as done.
    assert _post(client, ["county"]).json() == {"confirmed": 0, "pending": []}
    assert _reviewed(client, "county") is True


@pytest.mark.postgres
@pytest.mark.django_db
def test_get_is_rejected(variables):
    assert _session_client().get(URL).status_code == 405


@pytest.mark.postgres
@pytest.mark.django_db
def test_a_post_without_the_csrf_token_is_rejected_and_writes_nothing(
    variables,
):
    client = _session_client(enforce_csrf_checks=True)
    _store(client, "county", "Cass")
    response = _post(client, ["county"])
    assert response.status_code == 403
    assert _reviewed(client, "county") is False
