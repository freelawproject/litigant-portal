from copy import deepcopy
from datetime import UTC, date, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest
from django.http import Http404
from django.test import RequestFactory

from litigant_portal.agents import assistant
from litigant_portal.agents.assistant import LitigantAssistant
from litigant_portal.agents.base import TurnTimeContext
from litigant_portal.agents.tools import review_facts
from litigant_portal.app.models import (
    ChatThread,
    Topic,
    TopicFlow,
    TopicFlowDeadline,
    TopicFlowInterviewPage,
    TopicFlowInterviewVariable,
    TopicFlowSection,
    UserIdentity,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.selectors import state as selectors
from litigant_portal.app.selectors.state import (
    FlowStateType,
    court_rules,
    state_snapshot,
)
from litigant_portal.app.services import chat_engine
from litigant_portal.app.views import assistant as assistant_views
from litigant_portal.app.views import topic_flow as flow_views
from litigant_portal.app.views import utils as view_utils
from litigant_portal.state.projector import project


@pytest.fixture
def chat_flow(monkeypatch):
    gate = Variable(name="has_record", data_type="boolean")
    started = Variable(name="started_on", data_type="date", required=True)
    when = {"variable": gate.name, "value": True}
    pages = [
        TopicFlowInterviewPage(title="Your situation"),
        TopicFlowInterviewPage(title="Record details", when=when),
    ]
    for page, variable in zip(pages, (gate, started), strict=True):
        page._prefetched_objects_cache = {
            "variables": [
                TopicFlowInterviewVariable(page=page, variable=variable)
            ]
        }
    flow = TopicFlow(
        topic=Topic(court="test", slug="test", title="Test"),
        slug="standard",
        name="Test flow",
    )
    flow._prefetched_objects_cache = {
        "sections": [
            TopicFlowSection(
                key="record",
                heading="Record guidance",
                content="Conditional instructions.",
                when=when,
            )
        ],
        "interview_pages": pages,
        "form_conditions": [],
        "links": [],
        "deadlines": [
            TopicFlowDeadline(
                key="due",
                label="Due",
                offset_from=started,
                offset_days=10,
                when=when,
            )
        ],
    }
    identity = UserIdentity(id=1)
    thread = ChatThread(
        identity=identity, state={"active_topic_flow": "test/standard"}
    )
    monkeypatch.setattr(
        ChatThread.objects,
        "select_related",
        Mock(return_value=Mock(get=Mock(return_value=thread))),
    )
    monkeypatch.setattr(
        "litigant_portal.agents.assistant.topic_flow_from_path",
        Mock(return_value=flow),
    )
    monkeypatch.setattr(
        "litigant_portal.app.selectors.site.contact_list",
        Mock(return_value=[]),
    )
    monkeypatch.setattr(
        "litigant_portal.app.selectors.site.resource_list",
        Mock(return_value=[]),
    )
    public_ids = Mock(return_value={gate.pk, started.pk})
    monkeypatch.setattr(
        "litigant_portal.app.selectors.topic_flow.variable_public_ids",
        public_ids,
    )

    def snapshot(gate_value, *, include_started=True, reviewed=False):
        answers = {
            variable.name: VariableAnswer(
                variable=variable,
                value=value,
                reviewed=reviewed,
                updated_at=datetime(2026, 11, 25, tzinfo=UTC),
            )
            for variable, value in (
                (gate, gate_value),
                (started, "2026-11-25"),
            )
        }
        if not include_started:
            answers.pop(started.name)
        state = state_snapshot(
            identity=identity, flow=flow, answers=answers.values()
        )
        rules = court_rules(
            flow=flow, variables=[gate, started], contacts=[], resources=[]
        )
        current = FlowStateType(
            state,
            rules,
            project(state, rules, date(2026, 11, 25)),
            {v.name: v for v in (gate, started)},
            answers,
        )
        monkeypatch.setattr(
            selectors, "flow_state", Mock(return_value=current)
        )
        return current

    return thread, gate, started, public_ids, snapshot


def test_chat_projection_refreshes_applicability_and_masks_private_dates(
    chat_flow,
):
    thread, gate, started, public_ids, snapshot = chat_flow
    agent = LitigantAssistant()
    timing = TurnTimeContext(
        datetime(2026, 11, 26, 1, tzinfo=UTC),
        None,
        ZoneInfo("America/Los_Angeles"),
    )
    snapshot(True)
    prompt = agent.generate_identity_prompt(
        thread_id=thread.id, time_context=timing
    )
    assert "Conditional instructions." in prompt.text
    assert "2026-12-05" in prompt.text
    assert selectors.flow_state.call_args.kwargs["time_context"] == date(
        2026, 11, 25
    )
    public_ids.return_value = {gate.pk}
    stored = prompt.for_storage()
    assert "2026-12-05" not in stored["text"]
    assert 'value: "2026-11-25"' not in stored["text"]
    assert started.name not in stored["values"]
    snapshot(False)
    refreshed = agent.generate_identity_prompt(
        thread_id=thread.id, time_context=timing
    )
    assert "Conditional instructions." not in refreshed.text
    assert "Record details" not in refreshed.text
    assert started.name not in refreshed.values


def test_review_card_uses_projected_answers_and_requirements(
    chat_flow, monkeypatch
):
    thread, gate, started, _public_ids, snapshot = chat_flow
    monkeypatch.setattr(
        review_facts, "topic_flow_from_path", assistant.topic_flow_from_path
    )
    current = snapshot(False)
    data = review_facts.ReviewFacts()(thread_id=thread.id).render_data
    assert data["confirm_names"] == [gate.name]
    assert data["missing"] == []
    assert current.answers[started.name].value == "2026-11-25"
    snapshot(True, include_started=False)
    data = review_facts.ReviewFacts()(thread_id=thread.id).render_data
    assert data["missing"] == [{"name": started.name, "label": started.name}]
    snapshot(True)
    data = review_facts.ReviewFacts()(thread_id=thread.id).render_data
    assert data["confirm_names"] == [gate.name, started.name]


@pytest.mark.parametrize("owned", [True, False])
def test_briefcase_uses_only_the_owned_threads_applicable_facts(
    chat_flow, monkeypatch, owned
):
    thread, gate, _started, _public_ids, snapshot = chat_flow
    current = snapshot(False)
    request = RequestFactory().get(
        "/chat/briefcase/", {"thread_id": str(thread.pk)}
    )
    request.identity = thread.identity
    request.user = SimpleNamespace(is_authenticated=False)
    request.session = SimpleNamespace(session_key="owned")
    get_thread = (
        Mock(return_value=thread)
        if owned
        else Mock(side_effect=ChatThread.DoesNotExist)
    )
    monkeypatch.setattr(assistant_views, "chat_thread_get", get_thread)
    monkeypatch.setattr(
        assistant_views, "topic_flow_from_path", assistant.topic_flow_from_path
    )
    monkeypatch.setattr(view_utils, "flow_state", Mock(return_value=current))
    monkeypatch.setattr(
        assistant_views, "render", lambda request, template, context: context
    )
    if owned:
        result = assistant_views.briefcase(request)
        assert [
            answer.variable.name
            for group in result["briefcase_groups"]
            for answer in group["answers"]
        ] == [gate.name]
    else:
        with pytest.raises(Http404):
            assistant_views.briefcase(request)
    assert get_thread.call_args.kwargs["identity"] is thread.identity


@pytest.mark.parametrize(
    ("applicable", "reviewed"), [(False, True), (True, False), (True, True)]
)
def test_prefill_requires_projected_applicability_and_human_review(
    chat_flow, monkeypatch, applicable, reviewed
):
    thread, _gate, started, _public_ids, snapshot = chat_flow
    current = snapshot(applicable, reviewed=reviewed)
    flow = assistant.topic_flow_from_path("test/standard")
    flow.interview_reference = "docassemble.test:data/questions/form.yml"
    flow.interview_prefill = {started.name: "source_date"}
    request = RequestFactory().post("/t/test/test/standard/interview/")
    request.identity = thread.identity
    monkeypatch.setattr(
        flow_views, "topic_flow_row_get", Mock(return_value=flow)
    )
    monkeypatch.setattr(flow_views, "has_identity", Mock(return_value=True))
    monkeypatch.setattr(flow_views, "flow_state", Mock(return_value=current))
    monkeypatch.setattr(
        flow_views,
        "interview_launch_url",
        Mock(return_value="https://example.test/plain"),
    )
    launch = Mock(return_value="https://example.test/prefilled")
    monkeypatch.setattr(flow_views, "docassemble_session_create", launch)
    response = flow_views.topic_flow_interview(
        request, "test", "test", "standard"
    )
    if applicable and reviewed:
        assert launch.call_args.kwargs["variables"] == {
            "source_date": "2026-11-25"
        }
        assert response.url == "https://example.test/prefilled"
    else:
        launch.assert_not_called()
        assert response.url == "https://example.test/plain"


def test_outgoing_flow_history_is_replaced_without_changing_stored_history(
    monkeypatch,
):
    history = [
        {
            "role": "tool",
            "name": "LoadTopicFlow",
            "tool_call_id": "loaded",
            "content": "Old instructions [source:test/standard/old]",
        },
        {
            "role": "tool",
            "name": "LoadTopicFlow",
            "tool_call_id": "failed",
            "content": "Error: no such flow",
        },
        {"role": "user", "content": "Help."},
    ]
    original = deepcopy(history)
    outgoing = LitigantAssistant().history_for_model(history)
    assert "Old instructions" not in outgoing[0]["content"]
    assert outgoing[0]["tool_call_id"] == "loaded"
    assert outgoing[1:] == history[1:]
    assert history == original
    monkeypatch.setattr(
        chat_engine, "user_upload_llm_parts", Mock(return_value={})
    )
    messages = chat_engine._messages_for_llm(
        "Current guidance [source:test/standard/current]",
        outgoing,
        attachment_cache={},
        capabilities=frozenset(),
    )
    assert chat_engine._supplied_citation_ids(
        messages[0]["content"], messages[1:]
    ) == {"test/standard/current"}
