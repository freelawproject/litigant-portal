from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest

from litigant_portal.state.projector import project
from litigant_portal.state.rules import parse_condition
from litigant_portal.state.types import (
    CalendarRuleType,
    CourtRulesType,
    DeadlineRuleType,
    FactType,
    InformationRuleType,
    PacketEntryRuleType,
    PacketRuleType,
    QuestionsRuleType,
    StateType,
    VariableRuleType,
)

FLOW_ID = UUID(int=1)
TODAY = date(2026, 11, 25)
NOW = datetime(2026, 11, 25, tzinfo=UTC)
EXTRA = parse_condition({"variable": "needs_extra", "value": True})


@pytest.fixture
def rules():
    return CourtRulesType(
        flow_id=FLOW_ID,
        variables={
            "needs_extra": VariableRuleType(required=True),
            "detail": VariableRuleType(required=True, asked_when=EXTRA),
            "started_on": VariableRuleType(),
        },
        components=(
            InformationRuleType(id="intro", content="Read this first."),
            QuestionsRuleType(
                id="questions",
                content="Your situation",
                variables=("needs_extra", "detail"),
            ),
            QuestionsRuleType(
                id="dates",
                content="Optional dates",
                variables=("started_on",),
            ),
            PacketRuleType(
                id="packet",
                content="Forms",
                entries=(
                    PacketEntryRuleType(form="base"),
                    PacketEntryRuleType(form="extra", when=EXTRA),
                ),
            ),
            CalendarRuleType(
                id="calendar",
                content="Dates to remember",
                deadlines=(
                    DeadlineRuleType(
                        id="due",
                        offset_from="started_on",
                        offset_days=30,
                        when=EXTRA,
                    ),
                ),
            ),
        ),
    )


def _state(**values):
    return StateType(
        identity_id=1,
        flow_id=FLOW_ID,
        facts={
            name: FactType(value=value, reviewed=True, updated_at=NOW)
            for name, value in values.items()
        },
    )


def test_projection_retains_hidden_answers_and_restores_their_requirements(
    rules,
):
    state = _state(needs_extra=False, detail="Kept")
    before = state.model_dump()
    view = project(state, rules, TODAY)
    assert view.applicable_variables == ("needs_extra", "started_on")
    assert view.answered == ("needs_extra",)
    assert view.missing_required == view.unconfirmed == ()
    assert view.forms == ("base",)
    assert view.deadlines == ()
    assert state.model_dump() == before

    state.facts["needs_extra"] = FactType(
        value=True, reviewed=True, updated_at=NOW
    )
    state.facts["detail"] = FactType(
        value="Kept", reviewed=False, updated_at=NOW
    )
    view = project(state, rules, TODAY)
    assert view.applicable_variables == ("needs_extra", "detail", "started_on")
    assert view.unconfirmed == ("detail",)
    assert view.forms == ("base", "extra")
    assert view.deadlines[0].date is None


def test_viewing_skips_optional_questions_but_cannot_complete_required_ones(
    rules,
):
    state = _state(needs_extra=True)
    state.facts["started_on"] = FactType(value="2026-11-01", updated_at=NOW)
    view = project(state, rules, TODAY, limit=3)
    assert [c.component_id for c in view.candidates] == [
        "intro",
        "questions",
        "dates",
    ]
    assert all(c.score is None for c in view.candidates)
    assert view.missing_required == ("detail",)
    assert {c.id for c in view.components if not c.can_continue} == {
        "questions"
    }
    state.viewed.update({c.id: c.signature for c in view.components})
    view = project(state, rules, TODAY)
    assert [c.component_id for c in view.candidates] == ["questions"]

    state.facts["detail"] = FactType(value="Answer", updated_at=NOW)
    view = project(state, rules, TODAY)
    assert view.candidates[0].component_id == "questions"
    assert not next(
        c for c in view.components if c.id == "questions"
    ).can_continue
    state.facts["detail"] = FactType(
        value="Answer", reviewed=True, updated_at=NOW
    )
    view = project(state, rules, TODAY)
    assert view.candidates == ()
    assert all(c.can_continue for c in view.components)


def test_view_signatures_track_authored_content_and_resolved_outputs(rules):
    state = _state(needs_extra=False)
    initial = project(state, rules, TODAY)
    state.viewed.update({c.id: c.signature for c in initial.components})
    assert project(state, rules, TODAY).candidates == ()
    revised = rules.model_copy(
        update={
            "components": (
                rules.components[0].model_copy(
                    update={"content": "Updated guidance."}
                ),
                *rules.components[1:],
            )
        }
    )
    assert project(state, revised, TODAY).candidates[0].component_id == "intro"

    state.facts["needs_extra"] = FactType(
        value=True, reviewed=True, updated_at=NOW
    )
    view = project(state, rules, TODAY, limit=10)
    assert [c.component_id for c in view.candidates] == [
        "questions",
        "packet",
        "calendar",
    ]
    assert next(c for c in view.components if c.id == "intro").complete


def test_component_conditions_control_requirements_and_empty_outputs(rules):
    rules = rules.model_copy(
        update={
            "components": (
                rules.components[1].model_copy(update={"when": EXTRA}),
                PacketRuleType(id="empty", content="No available forms"),
                PacketRuleType(
                    id="launch", content="Interview", interview_available=True
                ),
            )
        }
    )
    view = project(_state(), rules, TODAY)
    assert view.applicable_variables == view.missing_required == ()
    assert [c.id for c in view.components] == ["launch"]


def test_deadlines_use_explicit_time_and_do_not_invent_missing_dates(rules):
    state = _state(needs_extra=True, started_on="2026-10-26")
    deadline = project(state, rules, TODAY).deadlines[0]
    assert deadline.date == TODAY
    assert not deadline.is_past
    assert (
        project(state, rules, TODAY + timedelta(days=1)).deadlines[0].is_past
    )
    state.facts["started_on"] = FactType(value="not a date", updated_at=NOW)
    deadline = project(state, rules, TODAY).deadlines[0]
    assert deadline.date is None
    assert not deadline.is_past


def test_projection_rejects_cross_flow_viewing_state_and_invalid_limits(rules):
    with pytest.raises(ValueError, match="flow"):
        project(
            _state().model_copy(update={"flow_id": UUID(int=2)}), rules, TODAY
        )
    with pytest.raises(ValueError, match="positive"):
        project(_state(), rules, TODAY, limit=0)
