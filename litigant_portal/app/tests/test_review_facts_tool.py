"""Tests for the ReviewFacts agent tool.

The tool reads the thread's active flow and the identity's stored answers,
so every test is postgres-marked. The safety rule under test: the tool
takes no input that could steer the card, and it never writes.
"""

import pytest

from litigant_portal.agents.tools.review_facts import ReviewFacts
from litigant_portal.app.models import (
    ChatThread,
    Topic,
    TopicFlow,
    TopicFlowInterviewPage,
    TopicFlowInterviewVariable,
    UserIdentity,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.services.chat_engine import chat_thread_state_merge
from litigant_portal.app.services.topic_flow import variable_answer_set
from litigant_portal.app.topic_flow import registry as registry_module
from litigant_portal.app.topic_flow.schema import (
    Corpus,
    FactGatherSection,
    Metadata,
    PacketOutput,
    Question,
)

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

TRACK = {"court": "test-court", "topic": "name-change", "role": "standard"}


@pytest.fixture
def thread():
    identity = UserIdentity.objects.create(session_key="review-facts")
    return ChatThread.objects.create(
        identity=identity, thread_type="user_chat"
    )


@pytest.fixture
def flow():
    topic = Topic.objects.create(slug="name_change", title="Name change")
    flow = TopicFlow.objects.create(
        topic=topic, slug="standard", name="Standard", enabled=True
    )
    page = TopicFlowInterviewPage.objects.create(flow=flow, title="About you")
    first_name = Variable.objects.create(
        name="first_name", label="First name", required=True
    )
    county = Variable.objects.create(
        name="county", label="County", required=True
    )
    has_alias = Variable.objects.create(
        name="has_alias",
        label="Other names",
        data_type=VariableDataType.BOOLEAN,
    )
    alias = Variable.objects.create(
        name="alias",
        label="Other name used",
        required=True,
        asked_when=has_alias,
        asked_when_value=True,
    )
    for order, variable in enumerate([first_name, county, has_alias, alias]):
        TopicFlowInterviewVariable.objects.create(
            page=page, variable=variable, order=order
        )
    # Answered but not on this flow: must stay off the card.
    Variable.objects.create(name="rent_amount", label="Rent")
    return flow


@pytest.fixture
def active_flow(thread, flow):
    chat_thread_state_merge(
        thread_id=thread.id,
        updates={"active_topic_flow": "name_change/standard"},
    )
    return flow


def _store(thread, name, value, reviewed=False):
    variable_answer_set(
        identity=thread.identity,
        variable=Variable.objects.get(name=name),
        value=value,
        reviewed=reviewed,
    )


def _launchable(monkeypatch, settings):
    settings.DOCASSEMBLE_BASE_URL = "https://da.example.gov"
    settings.DOCASSEMBLE_PUBLIC_URL = None
    corpus = Corpus(
        metadata=Metadata(
            court=TRACK["court"],
            topic=TRACK["topic"],
            role=TRACK["role"],
            title="T",
        ),
        sections=[
            PacketOutput(
                kind="output",
                output_type="packet",
                id="filing_packet",
                heading="Packet",
                forms=["Petition"],
                interview_reference=(
                    "docassemble.test:data/questions/petition.yml"
                ),
                interview_prefill={},
            )
        ],
    )
    monkeypatch.setattr(
        registry_module.registry, "tracks_for", lambda topic: [TRACK]
    )
    monkeypatch.setattr(registry_module.registry, "get", lambda *a: corpus)


def test_without_an_active_flow_the_tool_reports_an_error(thread, flow):
    output = ReviewFacts()(thread_id=thread.id)
    assert output.result.startswith("Error: no active topic flow")
    assert output.render_data is None


def test_answered_flow_variables_are_listed_with_their_review_state(
    thread, active_flow
):
    _store(thread, "first_name", "Sandra", reviewed=True)
    _store(thread, "county", "Cass")
    data = ReviewFacts()(thread_id=thread.id).render_data
    assert data["facts"] == [
        {
            "name": "first_name",
            "label": "First name",
            "value": "Sandra",
            "reviewed": True,
        },
        {
            "name": "county",
            "label": "County",
            "value": "Cass",
            "reviewed": False,
        },
    ]
    assert data["confirm_names"] == ["first_name", "county"]
    assert data["all_reviewed"] is False


def test_all_reviewed_is_true_only_when_every_listed_fact_is_confirmed(
    thread, active_flow
):
    _store(thread, "first_name", "Sandra", reviewed=True)
    assert ReviewFacts()(thread_id=thread.id).render_data["all_reviewed"]


def test_unanswered_required_variables_are_reported_missing(
    thread, active_flow
):
    _store(thread, "first_name", "Sandra")
    output = ReviewFacts()(thread_id=thread.id)
    assert output.render_data["missing"] == [
        {"name": "county", "label": "County"}
    ]
    assert "Still missing required facts: county" in output.result


def test_a_gated_variable_is_missing_only_when_its_gate_is_met(
    thread, active_flow
):
    _store(thread, "first_name", "Sandra")
    _store(thread, "county", "Cass")
    _store(thread, "has_alias", False)
    assert ReviewFacts()(thread_id=thread.id).render_data["missing"] == []

    _store(thread, "has_alias", True)
    assert ReviewFacts()(thread_id=thread.id).render_data["missing"] == [
        {"name": "alias", "label": "Other name used"}
    ]


def test_the_result_says_nothing_is_missing_and_only_the_user_confirms(
    thread, active_flow
):
    _store(thread, "first_name", "Sandra")
    _store(thread, "county", "Cass")
    output = ReviewFacts()(thread_id=thread.id)
    assert "No required facts are missing." in output.result
    assert "Only the user can confirm facts" in output.result


def test_answers_outside_the_active_flow_stay_off_the_card(
    thread, active_flow
):
    _store(thread, "rent_amount", "900")
    data = ReviewFacts()(thread_id=thread.id).render_data
    assert data["facts"] == []
    assert data["confirm_names"] == []


def test_a_cleared_answer_is_treated_as_unanswered(thread, active_flow):
    _store(thread, "county", "Cass")
    _store(thread, "county", None)
    data = ReviewFacts()(thread_id=thread.id).render_data
    assert data["facts"] == []
    assert {"name": "county", "label": "County"} in data["missing"]


def test_the_tool_takes_no_arguments_and_a_reviewed_flag_changes_nothing(
    thread, active_flow
):
    _store(thread, "county", "Cass")
    schema = ReviewFacts.get_schema()["function"]["parameters"]
    assert schema.get("properties", {}) == {}

    ReviewFacts(reviewed=True, names=["county"])(thread_id=thread.id)
    answer = VariableAnswer.objects.get(
        identity=thread.identity, variable__name="county"
    )
    assert answer.reviewed is False


def test_interview_is_available_when_page_corpus_and_docassemble_line_up(
    thread, active_flow, monkeypatch, settings
):
    _launchable(monkeypatch, settings)
    data = ReviewFacts()(thread_id=thread.id).render_data
    assert data["interview_available"] is True
    assert (data["court"], data["topic"], data["role"]) == (
        "test-court",
        "name-change",
        "standard",
    )


def test_interview_is_unavailable_without_docassemble(
    thread, active_flow, monkeypatch, settings
):
    _launchable(monkeypatch, settings)
    settings.DOCASSEMBLE_BASE_URL = None
    data = ReviewFacts()(thread_id=thread.id).render_data
    assert data["interview_available"] is False
    assert data["court"] == "test-court"


def test_interview_is_unavailable_when_the_corpus_has_no_interview(
    thread, active_flow, monkeypatch, settings
):
    _launchable(monkeypatch, settings)
    corpus = Corpus(
        metadata=Metadata(court="c", topic="t", role="r", title="T"),
        sections=[
            FactGatherSection(
                kind="fact_gather",
                id="your_information",
                heading="Your name",
                questions=[Question(id="first_name", label="First name")],
            )
        ],
    )
    monkeypatch.setattr(registry_module.registry, "get", lambda *a: corpus)
    assert not ReviewFacts()(thread_id=thread.id).render_data[
        "interview_available"
    ]


def test_interview_is_unavailable_when_no_registry_page_matches(
    thread, active_flow, monkeypatch, settings
):
    _launchable(monkeypatch, settings)
    monkeypatch.setattr(
        registry_module.registry, "tracks_for", lambda topic: []
    )
    data = ReviewFacts()(thread_id=thread.id).render_data
    assert data["interview_available"] is False
    assert data["court"] is None
