"""
Preparation requirements preserve missing values and conditional questions.
"""

from lp_agent.flows.checks import AgentChecker
from lp_agent.preparation import PhaseMaterial, PhaseProgress


def test_false_zero_and_optional_values_are_not_missing():
    phase = {
        "facts": [
            {"required": True, "definition": {"key": "waiver"}},
            {"required": True, "definition": {"key": "months"}},
            {"required": False, "definition": {"key": "future_date"}},
            {
                "required": True,
                "definition": {"key": "details"},
                "condition": {"variable": "convicted", "value": True},
            },
        ]
    }
    phase["id"], phase["key"], phase["title"] = "phase-id", "phase", "Phase"
    for fact in phase["facts"]:
        fact["definition"].update(
            id=fact["definition"]["key"], scope="matter", value_schema={}
        )
    material = PhaseMaterial.model_validate(phase)
    assert (
        AgentChecker.phase_requirements(
            material, {"waiver": False, "months": 0, "convicted": False}
        )
        == ()
    )
    assert AgentChecker.phase_requirements(
        material, {"waiver": False, "months": 0, "convicted": True}
    ) == ("details",)
    assert AgentChecker.phase_requirements(material, {"waiver": False}) == (
        "months",
    )


def test_completion_uses_phase_state():
    assert AgentChecker.check_finished(()) == (False, 0)
    assert AgentChecker.check_finished(
        tuple(
            PhaseProgress(
                key="phase",
                title="Phase",
                state=state,
                missing=(),
                acknowledgement_required=False,
            )
            for state in ("completed", "active")
        )
    ) == (False, 50)
