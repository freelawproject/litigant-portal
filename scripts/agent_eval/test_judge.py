"""
Keep evaluator citation support tied to captured material for the final answer.
"""

import json
import unittest

from .judge import FORMAT_VERSION, InvalidGrade, cited_sources, parse_response
from .schema import DIMENSIONS, Weights


def review_call(answer, sources, **context):
    return {
        "request": {
            "instructions": "You review candidate answers from a legal assistant.",
            "input": [
                {
                    "content": json.dumps(
                        {
                            "candidate": answer,
                            "material": {"sources": sources},
                            **context,
                        }
                    )
                }
            ],
        },
        "response": {"approved": True},
    }


class CitedSourceTests(unittest.TestCase):
    def test_only_cited_material_reaches_external_judge(self):
        answer = "The fee is $18.87. [source:guide-a] [source:invented]"
        source = {
            "source_id": "guide-a",
            "kind": "corpus",
            "title": "Fictional guide A",
            "locator": "/t/eval-ohio/chickens-a/protection/",
            "content": "The fictional filing fee is $18.87.",
        }
        record = {
            "answer": answer,
            "calls": [
                review_call(
                    answer,
                    [
                        {**source, "private_metadata": "Do not forward"},
                        {**source, "source_id": "uncited"},
                    ],
                    previous_reviews=[{"candidate": "Rejected draft"}],
                    conversation=[{"text": "Private conversation"}],
                )
            ],
        }
        self.assertEqual(cited_sources(record), [source])

    def test_uses_matching_final_answer_not_rejected_draft(self):
        answer = "The fee is $42. [source:guide]"
        source = {"source_id": "guide", "content": "Fee: $42."}
        other = {"source_id": "guide", "content": "Fee: $18.87."}
        record = {
            "answer": answer,
            "calls": [
                review_call("An earlier draft.", [other]),
                review_call(answer, [source]),
                review_call("An unrelated answer.", [other]),
            ],
        }
        self.assertEqual(cited_sources(record), [source])
        record["answer"] = "An unreviewed answer. [source:guide]"
        self.assertEqual(cited_sources(record), [])

    def test_candidate_written_sources_are_not_corpus_evidence(self):
        answer = "The fee is $0. [source:invented]"
        call = review_call(
            answer, [{"source_id": "invented", "content": "Fee: $0."}]
        )
        call["request"]["instructions"] = "Answer the user's question."
        self.assertEqual(
            cited_sources({"answer": answer, "calls": [call]}), []
        )

    def test_missing_records_and_malformed_inputs_provide_no_evidence(self):
        answer = "An answer. [source:guide]"
        for calls in (None, [], [{"request": {}}], [review_call(answer, [])]):
            with self.subTest(calls=calls):
                record = {"answer": answer}
                if calls is not None:
                    record["calls"] = calls
                self.assertEqual(cited_sources(record), [])
        call = review_call(answer, [])
        for value in ([], [{"content": "invalid JSON"}], "other API format"):
            with self.subTest(value=value):
                call["request"]["input"] = value
                self.assertEqual(
                    cited_sources({"answer": answer, "calls": [call]}), []
                )

    def test_source_id_without_content_is_not_support(self):
        answer = "An answer. [source:guide]"
        call = review_call(answer, [{"source_id": "guide"}])
        self.assertEqual(
            cited_sources({"answer": answer, "calls": [call]}), []
        )


class CitedValueTests(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "answer": "Ask the clerk about the procedure.",
            "case": {
                "id": "example",
                "group": "real",
                "court": "example",
                "topic": "example",
                "question": "What is the procedure?",
                "references": ["example.yml"],
                "facts": [{"id": "procedure", "statement": "Explain it."}],
                "acceptable_deferral": "Ask the clerk.",
            },
        }
        self.response = {
            "dimensions": {
                name: {"score": 3, "explanation": "Example assessment."}
                for name in DIMENSIONS
            },
            "answer_outcome": "partial",
            "source_attribution": "absent",
            "facts": [
                {
                    "fact_id": "procedure",
                    "status": "omitted",
                    "evidence_ids": [],
                    "explanation": "The answer omits the required procedure.",
                }
            ],
            "deal_breakers": [],
        }

    def parse(self):
        return parse_response(
            json.dumps(self.response),
            self.candidate,
            Weights(),
            FORMAT_VERSION,
        )

    def test_missing_nullable_value_preserves_omission(self):
        fact = self.parse()["grade"]["facts"][0]
        self.assertIsNone(fact["value"])
        self.assertEqual(fact["status"], "omitted")
        self.assertEqual(fact["evidence"], "")

    def test_nonnumeric_supported_fact_may_omit_value(self):
        self.response["facts"][0].update(status="supported", evidence_ids=[1])
        self.assertIsNone(self.parse()["grade"]["facts"][0]["value"])

    def test_unasserted_numeric_fact_does_not_copy_answer_key(self):
        self.candidate["case"]["facts"][0]["value"] = 30
        for status in ("omitted", "uncertain"):
            with self.subTest(status=status):
                self.response["facts"][0]["status"] = status
                self.assertIsNone(self.parse()["grade"]["facts"][0]["value"])

    def test_asserted_numeric_or_boolean_fact_still_requires_value(self):
        for expected in (30, True):
            for status in ("supported", "contradicted"):
                with self.subTest(expected=expected, status=status):
                    self.candidate["case"]["facts"][0]["value"] = expected
                    self.response["facts"][0].update(
                        status=status, evidence_ids=[1]
                    )
                    with self.assertRaises(InvalidGrade) as raised:
                        self.parse()
                    self.assertEqual(
                        raised.exception.category, "missing_value"
                    )

    def test_explicit_value_on_omitted_fact_is_still_rejected(self):
        self.response["facts"][0]["value"] = 0
        with self.assertRaises(InvalidGrade) as raised:
            self.parse()
        self.assertEqual(raised.exception.category, "unexpected_value")

    def test_false_and_zero_are_not_treated_as_missing(self):
        for value in (False, 0):
            with self.subTest(value=value):
                self.candidate["case"]["facts"][0]["value"] = value
                self.response["facts"][0].update(
                    status="supported", evidence_ids=[1], value=value
                )
                self.assertIsNotNone(
                    self.parse()["grade"]["facts"][0]["value"]
                )
