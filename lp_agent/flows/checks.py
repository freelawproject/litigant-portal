"""
Deterministic preparation checks and limited, observational wording checks.
"""

import re

from pydantic import JsonValue

from lp_agent.preparation import PhaseMaterial, PhaseProgress


class AgentChecker:
    """
    Check data requirements, never infer legal completion from prose.
    """

    @staticmethod
    def upl_findings(output: str) -> list[str]:
        """
        Flag a few obvious claims; this is not a legal-advice classifier.
        """
        patterns = {
            "attorney_claim": r"\bI am your (?:lawyer|attorney)\b",
            "guaranteed_outcome": r"\b(?:you will definitely win|guarantee (?:you|your))\b",
        }
        return [
            key
            for key, pattern in patterns.items()
            if re.search(pattern, output, re.I)
        ]

    @classmethod
    def check_upl(cls, output: str) -> bool:
        return bool(output.strip()) and not cls.upl_findings(output)

    @staticmethod
    def phase_requirements(
        phase: PhaseMaterial, facts: dict[str, JsonValue]
    ) -> tuple[str, ...]:
        return tuple(
            item.definition.key
            for item in phase.facts
            if item.required
            and (item.condition is None or item.condition.matches(facts))
            and (
                item.definition.key not in facts
                or facts[item.definition.key] in (None, "")
            )
        )

    @staticmethod
    def check_finished(phases: tuple[PhaseProgress, ...]) -> tuple[bool, int]:
        done = sum(phase.state == "completed" for phase in phases)
        return bool(phases) and done == len(phases), round(
            100 * done / len(phases)
        ) if phases else 0
