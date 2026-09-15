"""
Keep evaluator citation support tied to captured material for the final answer.
"""

import json
import unittest

from .judge import cited_sources


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
