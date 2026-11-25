from datetime import UTC, date, datetime
from unittest.mock import Mock

import pytest
from django.test import RequestFactory

from litigant_portal.app.models import (
    Form,
    Topic,
    TopicFlow,
    TopicFlowDeadline,
    TopicFlowFormCondition,
    TopicFlowInterviewPage,
    TopicFlowInterviewVariable,
    TopicFlowSection,
    UserIdentity,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.selectors.state import (
    FlowStateType,
    court_rules,
    state_snapshot,
)
from litigant_portal.app.topic_flow import rows
from litigant_portal.app.views import topic_flow as views
from litigant_portal.state.projector import project


def _prefetched(row, **relations):
    row._prefetched_objects_cache = relations
    return row


@pytest.fixture
def stored_flow():
    gate = Variable(name="needs_help", data_type="boolean", required=True)
    started = Variable(name="started_on", data_type="date")
    condition = {"not": {"variable": gate.name, "value": False}}
    section = TopicFlowSection(
        key="help", heading="Help", content="Read.", when=condition
    )
    page = _prefetched(
        TopicFlowInterviewPage(title="Your situation", on_page=False),
        variables=[
            TopicFlowInterviewVariable(variable=v) for v in (gate, started)
        ],
    )
    flow = _prefetched(
        TopicFlow(
            topic=Topic(court="test", slug="test"),
            slug="standard",
            layout=["interview", "help", "packet", "calendar"],
        ),
        sections=[section],
        interview_pages=[page],
        form_conditions=[
            TopicFlowFormCondition(
                form=Form(slug="help-form", name="Help form"), when=condition
            )
        ],
        deadlines=[
            TopicFlowDeadline(
                key="due",
                label="Due",
                offset_from=started,
                offset_days=10,
                when=condition,
            )
        ],
    )
    return flow, gate, started, section


def test_stored_graph_projects_all_pages_and_invalidates_edited_content(
    stored_flow,
):
    flow, gate, started, section = stored_flow
    now = datetime(2026, 11, 25, tzinfo=UTC)
    answers = [
        VariableAnswer(variable=v, value=value, reviewed=True, updated_at=now)
        for v, value in ((gate, True), (started, "2026-11-01"))
    ]
    state = state_snapshot(
        identity=UserIdentity(id=1), flow=flow, answers=answers
    )
    rules = court_rules(
        flow=flow, variables=[gate, started], contacts=[], resources=[]
    )
    projection = project(state, rules, now.date(), limit=4)
    assert [c.id for c in projection.components] == [
        "interview-1",
        "help",
        "packet",
        "calendar",
    ]
    assert projection.components[0].complete
    assert projection.forms == ("help-form",)
    assert projection.deadlines[0].date == date(2026, 11, 11)
    assert projection.deadlines[0].is_past
    assert state.facts[gate.name].updated_at == now

    rendered = rows.render_flow(
        flow,
        [section],
        rows.flow_pages(flow),
        {a.variable.name: a.value for a in answers},
        projection=projection,
        form_conditions=flow.form_conditions.all(),
        deadlines=flow.deadlines.all(),
    )
    assert [s.anchor_id for s in rendered] == [
        c.id for c in projection.components
    ]
    assert rendered[3].context["deadlines"][0]["date_iso"] == "2026-11-11"

    signature = projection.components[1].signature
    state = state_snapshot(
        identity=UserIdentity(id=1),
        flow=flow,
        answers=answers,
        viewed={"help": signature},
    )
    assert project(state, rules, now.date()).components[1].complete
    section.content = "Updated instructions."
    revised = court_rules(
        flow=flow, variables=[gate, started], contacts=[], resources=[]
    )
    assert not project(state, revised, now.date()).components[1].complete
    assert state.viewed == {"help": signature}


@pytest.mark.parametrize(
    ("action", "selected", "stale", "reviewed", "bad_date", "marks_view"),
    [
        ("", "", False, True, False, False),
        ("", "help", False, True, False, False),
        ("continue", "help", False, True, False, True),
        ("continue", "help", True, True, False, False),
        ("continue", "interview-1", False, False, False, False),
        ("continue", "interview-1", False, True, False, True),
        ("save", "interview-1", False, True, False, True),
        ("save", "interview-1", False, True, True, False),
    ],
)
def test_guided_selection_and_human_actions(
    stored_flow,
    monkeypatch,
    action,
    selected,
    stale,
    reviewed,
    bad_date,
    marks_view,
):
    flow, gate, started, _section = stored_flow
    identity = UserIdentity(id=1)
    state = state_snapshot(
        identity=identity,
        flow=flow,
        answers=[
            VariableAnswer(
                variable=gate,
                value=True,
                reviewed=reviewed,
                updated_at=datetime(2026, 11, 25, tzinfo=UTC),
            )
        ],
    )
    rules = court_rules(
        flow=flow, variables=[gate, started], contacts=[], resources=[]
    )
    current = FlowStateType(
        state,
        rules,
        project(state, rules, date(2026, 11, 25)),
        {v.name: v for v in (gate, started)},
        {},
    )
    for name, value in {
        "topic_flow_row_get": flow,
        "contact_list": [],
        "resource_list": [],
        "flow_state": current,
        "briefcase_answers": [],
        "has_identity": True,
    }.items():
        monkeypatch.setattr(views, name, Mock(return_value=value))
    monkeypatch.setattr(
        views, "render", lambda request, template, context: context
    )
    monkeypatch.setattr(views.messages, "info", Mock())
    monkeypatch.setattr(views.messages, "success", Mock())
    save, viewed = Mock(), Mock()
    monkeypatch.setattr(views, "variable_answer_set_many", save)
    monkeypatch.setattr(views, "topic_flow_section_viewed", viewed)
    data = {"component": selected}
    if action:
        component = next(
            c for c in current.projection.components if c.id == selected
        )
        data.update(
            action=action,
            signature="stale" if stale else component.signature,
            needs_help="true",
            started_on="bad" if bad_date else "2026-11-01",
            unrelated="ignore",
        )
    factory = RequestFactory()
    request = (
        factory.post("/t/test/test/standard/", data)
        if action
        else factory.get("/t/test/test/standard/", data)
    )
    request.identity = identity
    response = views.topic_flow(request, "test", "test", "standard")
    assert viewed.called is marks_view
    if action == "save":
        assert save.call_args.kwargs["values"] == (
            {"needs_help": True}
            if bad_date
            else {"needs_help": True, "started_on": "2026-11-01"}
        )
        assert save.call_args.kwargs["reviewed"] is True
        if bad_date:
            question = response["rendered_sections"][0].context["questions"][1]
            assert question["errors"] and question["autofocus"]
    else:
        save.assert_not_called()
    if not action:
        assert [s.anchor_id for s in response["rendered_sections"]] == [
            selected or "interview-1"
        ]
        assert [link["anchor"] for link in response["section_links"]] == [
            c.id for c in current.projection.components
        ]
    elif not bad_date:
        assert response.status_code == 302
