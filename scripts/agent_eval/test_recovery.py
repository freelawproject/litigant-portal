"""
Verify recovery and failure reporting using saved synthetic records only.
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import judge, runner
from .report import candidate_error, summarize
from .schema import DIMENSIONS, Config, write_json


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = Config(
            systems=["new"], models=["luna"], cases=["nd-fee"], repetitions=3
        )
        self.run, cases = runner.make_run(self.config, Path(temporary.name))
        case = cases[0].model_dump()
        self.response = {
            "dimensions": {
                name: {"score": 3, "explanation": "Example assessment."}
                for name in DIMENSIONS
            },
            "answer_outcome": "partial",
            "source_attribution": "absent",
            "facts": [
                {
                    "fact_id": fact["id"],
                    "status": "omitted",
                    "evidence_ids": [],
                    "explanation": "The requested fact is omitted.",
                    "value": None,
                }
                for fact in case["facts"]
            ],
            "deal_breakers": [],
        }
        self.paths = [f"new-luna/nd-fee-r{i}.json" for i in range(1, 4)]
        manifest_path = self.run / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["attempts"] = self.paths
        write_json(manifest_path, manifest)
        self.batch = self.run / "judgments" / "00000000-original"
        judgments = {}
        for i, path in enumerate(self.paths):
            candidate = {
                "system": "new",
                "model": "luna",
                "repeat": i + 1,
                "case": case,
                "status": "completed" if i < 2 else "error",
                "answer": "Ask the clerk." if i < 2 else "",
                "calls": [{"cost_usd": 0.01}],
                "events": [],
            }
            if i == 2:
                candidate.update(
                    error="RuntimeError: Agent ended in state failed.",
                    error_category="RuntimeError",
                    events=[
                        {
                            "type": "outcome",
                            "outcome": {
                                "state": "failed",
                                "error": {
                                    "code": "response_rejected",
                                    "message": "No answer passed review.",
                                },
                            },
                        }
                    ],
                )
            write_json(self.run / path, candidate)
            if i == 2:
                continue
            response = json.loads(json.dumps(self.response))
            if i == 1:
                del response["facts"][-1]["value"]
            record = {
                "candidate": path,
                "status": "completed" if i == 0 else "error",
                "config": self.config.model_dump(),
                "calls": [{"cost_usd": 0.02}],
                "raw_judge_text": json.dumps(response),
                "judge_format_version": judge.FORMAT_VERSION,
                "answer_passages": judge.answer_passages(candidate["answer"]),
            }
            if i == 0:
                record.update(
                    judge.parse_response(
                        record["raw_judge_text"],
                        candidate,
                        self.config.weights,
                        judge.FORMAT_VERSION,
                    )
                )
            else:
                record.update(
                    error="Missing value.", error_category="ValidationError"
                )
            name = Path(path).name
            judgments[path] = name
            write_json(self.batch / name, record)
        write_json(
            self.batch / "batch.json",
            {
                "status": "incomplete",
                "config": self.config.model_dump(),
                "judgments": judgments,
            },
        )

    def test_candidate_failure_is_separate_from_grading_error(self):
        result = summarize(self.run)
        self.assertEqual(result["candidate_errors"], {"response_rejected": 1})
        self.assertEqual(result["grading"]["errors"], {"ValidationError": 1})
        self.assertEqual(
            result["grading"]["counts"], {"completed": 1, "error": 1}
        )
        self.assertEqual(result["systems"][0]["execution_failures"], 1)
        self.assertEqual(result["systems"][0]["ungraded"], 1)

    def test_recovery_preserves_originals_scores_and_paid_call_counts(self):
        originals = {
            path: path.read_bytes()
            for path in self.run.rglob("*")
            if path.is_file()
        }
        before = summarize(self.run)
        with (
            patch.object(
                judge, "evaluate", side_effect=AssertionError("No API calls")
            ),
            patch.object(
                runner,
                "execute_worker",
                side_effect=AssertionError("No workers"),
            ),
            patch.object(
                runner.systems,
                "invoke",
                side_effect=AssertionError("No candidates"),
            ),
        ):
            recovered = runner.recover_run(self.run)
        for path, content in originals.items():
            self.assertEqual(path.read_bytes(), content)
        after = summarize(self.run)
        self.assertEqual(after["grading"]["counts"], {"completed": 2})
        self.assertEqual(after["grading"]["errors"], {})
        self.assertEqual(after["grading"]["recovered"], 1)
        self.assertEqual(after["candidate_errors"], {"response_rejected": 1})
        self.assertEqual(after["systems"][0]["execution_failures"], 1)
        self.assertEqual(after["systems"][0]["ungraded"], 0)
        self.assertEqual(
            before["evaluator_totals_all_batches"],
            after["evaluator_totals_all_batches"],
        )
        batch = json.loads((recovered / "batch.json").read_text())
        retained = (recovered / batch["judgments"][self.paths[0]]).resolve()
        self.assertEqual(retained, (self.batch / "nd-fee-r1.json").resolve())

    def test_failure_without_agent_outcome_uses_recorded_error(self):
        record = {"status": "interrupted", "error": "Timed out."}
        self.assertEqual(
            candidate_error(record),
            {"code": "interrupted", "message": "Timed out."},
        )
        self.assertIsNone(candidate_error({"status": "completed"}))
