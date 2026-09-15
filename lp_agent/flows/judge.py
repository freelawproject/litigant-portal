"""
Observable judge/retry placeholders for the local demonstration.
"""

import logging

from pydantic import JsonValue

logger = logging.getLogger(__name__)


class AgentJudge:
    """
    Describe the future check without making a model call or reporting a pass.
    """

    @staticmethod
    def check_upl(
        *, run_id: str, findings: list[str], check_counter: int = 0
    ) -> dict[str, JsonValue]:
        result: dict[str, JsonValue] = {
            "status": "skipped",
            "mode": "demo_stub",
            "would_check": ["legal_information_boundary", "corpus_grounding"],
            "algorithmic_findings": list(findings),
            "check_counter": check_counter,
            "correction_limit": 3,
            "would_retry": bool(findings) and check_counter < 3,
            "would_stop": bool(findings) and check_counter >= 3,
        }
        logger.info(
            "Agent judge/retry stub (run_id=%s, status=skipped, findings=%s, would_retry=%s, correction_limit=3)",
            run_id,
            findings,
            result["would_retry"],
        )
        return result
