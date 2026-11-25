from datetime import UTC, date, datetime

from litigant_portal.app.models import (
    Form,
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
from litigant_portal.app.selectors.state import court_rules, state_snapshot
from litigant_portal.state.projector import project


def _prefetched(row, **relations):
    row._prefetched_objects_cache = relations
    return row


def test_stored_graph_projects_all_pages_and_invalidates_edited_content():
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
        TopicFlow(layout=["interview", "help", "packet", "calendar"]),
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
