"""The prefill handoff endpoint: POST -> session -> redirect.

Covers the guided-flow and assistant-flow scenarios on #804 with the
docassemble client mocked. The client's own contract is tested in
test_docassemble_client.py. The routing tests are DB-free; the rest read
stored answers, so they need a database (``make test``).
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import resolve, reverse

from litigant_portal.app.models import UserIdentity, Variable
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.services.docassemble import DocassembleError
from litigant_portal.app.services.topic_flow import variable_answer_set
from litigant_portal.app.topic_flow.schema import (
    Corpus,
    FactGatherSection,
    Metadata,
    PacketOutput,
    Question,
)
from litigant_portal.app.views import topic_flow as topic_flow_views

COURT, TOPIC, ROLE = "test-court", "test_topic", "petitioner"
URL = f"/t/{COURT}/{TOPIC}/{ROLE}/interview/"
FLOW_URL = f"/t/{COURT}/{TOPIC}/{ROLE}/"
INTERVIEW = "https://da.example.gov/interview/interview?i=petition.yml"
RESUME = "https://da.example.gov/interview/launch?c=token"
MAPPING = {
    "first_name": "current_first",
    "filing_county": "residence_county",
}


def _corpus(*, mapping=None, interview_url=INTERVIEW):
    return Corpus(
        metadata=Metadata(court=COURT, topic=TOPIC, role=ROLE, title="T"),
        sections=[
            FactGatherSection(
                kind="fact_gather",
                id="your_information",
                heading="Your name",
                questions=[
                    Question(id="first_name", label="First name"),
                    Question(id="filing_county", label="County"),
                ],
            ),
            PacketOutput(
                kind="output",
                output_type="packet",
                id="filing_packet",
                heading="Your filing packet",
                forms=["Petition"],
                interview_url=interview_url,
                interview_prefill=MAPPING if mapping is None else mapping,
            ),
        ],
    )


@pytest.fixture
def variables(db):
    Variable.objects.create(name="first_name", data_type=VariableDataType.TEXT)
    Variable.objects.create(
        name="filing_county", data_type=VariableDataType.TEXT
    )


class _Client:
    """Stands in for docassemble_session_create, recording its payload."""

    def __init__(self, resume_url=RESUME, error=None):
        self.resume_url = resume_url
        self.error = error
        self.calls = []

    def __call__(self, *, interview_url, variables):
        self.calls.append(
            {"interview_url": interview_url, "variables": variables}
        )
        if self.error:
            raise self.error
        return self.resume_url


@pytest.fixture
def docassemble(monkeypatch):
    client = _Client()
    monkeypatch.setattr(topic_flow_views, "docassemble_session_create", client)
    return client


def _flow(monkeypatch, **kwargs):
    monkeypatch.setattr(
        topic_flow_views.registry, "get", lambda *a: _corpus(**kwargs)
    )


def _identity(client):
    identity, _ = UserIdentity.objects.get_or_create(
        user=None, session_key=client.session.session_key
    )
    return identity


def _store(client, name, value, reviewed):
    variable_answer_set(
        identity=_identity(client),
        variable=Variable.objects.get(name=name),
        value=value,
        reviewed=reviewed,
    )


# --- routing (DB-free) ------------------------------------------------------


def test_interview_url_resolves_to_the_handoff_view():
    assert resolve(URL).view_name == "pages:topic_flow_interview"


def test_interview_url_reverses():
    assert (
        reverse(
            "pages:topic_flow_interview",
            kwargs={"court": COURT, "topic": TOPIC, "role": ROLE},
        )
        == URL
    )


# --- guided flow (needs DB) -------------------------------------------------


@pytest.mark.django_db
def test_post_redirects_to_the_one_time_resume_url(
    client, monkeypatch, docassemble, variables
):
    _flow(monkeypatch)
    response = client.post(URL)
    assert response.status_code == 302
    assert response["Location"] == RESUME


@pytest.mark.django_db
def test_reviewed_answers_are_sent_under_their_interview_names(
    client, monkeypatch, docassemble, variables
):
    _flow(monkeypatch)
    _store(client, "first_name", "Sandra", reviewed=True)
    _store(client, "filing_county", "Burleigh", reviewed=True)
    client.post(URL)
    assert docassemble.calls[0]["variables"] == {
        "current_first": "Sandra",
        "residence_county": "Burleigh",
    }


@pytest.mark.django_db
def test_an_unanswered_question_is_left_for_the_interview_to_ask(
    client, monkeypatch, docassemble, variables
):
    _flow(monkeypatch)
    _store(client, "first_name", "Sandra", reviewed=True)
    client.post(URL)
    assert docassemble.calls[0]["variables"] == {"current_first": "Sandra"}


@pytest.mark.django_db
def test_a_fresh_guest_hands_over_an_empty_payload(
    client, monkeypatch, docassemble
):
    # Equal to today's plain link-out, and no identity row minted for a
    # visitor who answered nothing.
    _flow(monkeypatch)
    assert client.post(URL)["Location"] == RESUME
    assert docassemble.calls[0]["variables"] == {}
    assert UserIdentity.objects.count() == 0


@pytest.mark.django_db
def test_a_changed_answer_is_sent_at_its_new_value(
    client, monkeypatch, docassemble, variables
):
    _flow(monkeypatch)
    _store(client, "first_name", "Sandra", reviewed=True)
    _store(client, "first_name", "Alex", reviewed=True)
    client.post(URL)
    assert docassemble.calls[0]["variables"] == {"current_first": "Alex"}


@pytest.mark.django_db
def test_the_launch_url_from_the_corpus_is_what_gets_prefilled(
    client, monkeypatch, docassemble, variables
):
    _flow(monkeypatch)
    client.post(URL)
    assert docassemble.calls[0]["interview_url"] == INTERVIEW


@pytest.mark.django_db
def test_an_unmapped_flow_still_hands_off_with_no_variables(
    client, monkeypatch, docassemble, variables
):
    _flow(monkeypatch, mapping={})
    _store(client, "first_name", "Sandra", reviewed=True)
    client.post(URL)
    assert docassemble.calls[0]["variables"] == {}


# --- fallback (needs DB) ----------------------------------------------------


@pytest.mark.django_db
def test_a_failed_session_falls_back_to_the_plain_interview_link(
    client, monkeypatch, variables
):
    # No API key, docassemble down, a timeout: all arrive as DocassembleError,
    # and all must leave the litigant with a working link.
    monkeypatch.setattr(
        topic_flow_views,
        "docassemble_session_create",
        _Client(error=DocassembleError("no key")),
    )
    _flow(monkeypatch)
    response = client.post(URL)
    assert response.status_code == 302
    assert response["Location"] == INTERVIEW


@pytest.mark.django_db
def test_an_unexpected_client_error_is_not_swallowed(
    client, monkeypatch, variables
):
    # Only DocassembleError means "fall back"; a bug in our own code must
    # surface rather than hide behind an unprefilled interview.
    monkeypatch.setattr(
        topic_flow_views,
        "docassemble_session_create",
        _Client(error=TypeError("bug")),
    )
    _flow(monkeypatch)
    with pytest.raises(TypeError):
        client.post(URL)


# --- guards (needs DB) ------------------------------------------------------


@pytest.mark.django_db
def test_get_is_rejected(client, monkeypatch, docassemble, variables):
    # Creating a session is a side effect, so a crawler or a reload must not
    # be able to fire one.
    _flow(monkeypatch)
    assert client.get(URL).status_code == 405
    assert docassemble.calls == []


@pytest.mark.django_db
def test_unknown_flow_returns_404(client, monkeypatch, docassemble):
    monkeypatch.setattr(topic_flow_views.registry, "get", lambda *a: None)
    assert client.post(URL).status_code == 404
    assert docassemble.calls == []


@pytest.mark.django_db
def test_a_flow_without_an_interview_returns_404(
    client, monkeypatch, docassemble
):
    _flow(monkeypatch, interview_url=None)
    assert client.post(URL).status_code == 404
    assert docassemble.calls == []


# --- assistant flow (needs DB) ----------------------------------------------
# The trust boundary. An answer no human has confirmed must not reach a court
# form, since prefilling a variable skips the question that would show it.


@pytest.mark.django_db
def test_an_unreviewed_answer_is_never_sent(
    client, monkeypatch, docassemble, variables
):
    _flow(monkeypatch)
    _store(client, "first_name", "Sandra", reviewed=False)
    client.post(URL)
    assert docassemble.calls[0]["variables"] == {}


@pytest.mark.django_db
def test_the_same_answer_is_sent_once_the_litigant_confirms_it(
    client, monkeypatch, docassemble, variables
):
    _flow(monkeypatch)
    _store(client, "first_name", "Sandra", reviewed=False)
    client.post(FLOW_URL, {"first_name": "Sandra", "filing_county": ""})
    client.post(URL)
    assert docassemble.calls[0]["variables"] == {"current_first": "Sandra"}


@pytest.mark.django_db
def test_an_assistant_overwrite_drops_a_confirmed_answer_again(
    client, monkeypatch, docassemble, variables
):
    _flow(monkeypatch)
    _store(client, "first_name", "Sandra", reviewed=True)
    _store(client, "first_name", "Alex", reviewed=False)
    client.post(URL)
    assert docassemble.calls[0]["variables"] == {}


@pytest.mark.django_db
def test_answers_still_reach_the_payload_after_login(
    client, monkeypatch, docassemble, variables
):
    _flow(monkeypatch)
    client.post(FLOW_URL, {"first_name": "Sandra", "filing_county": ""})
    client.get(FLOW_URL)
    user = get_user_model().objects.create_user(username="u", password="p")
    assert client.login(username="u", password="p")
    client.post(URL)
    assert docassemble.calls[0]["variables"] == {"current_first": "Sandra"}
    assert UserIdentity.objects.filter(user=user).exists()
