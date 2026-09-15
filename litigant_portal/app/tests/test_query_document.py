"""
The document reader keeps its response and cost behavior with a deferred SDK.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from litigant_portal.agents.tools.query_document import QueryDocument


@pytest.mark.parametrize(
    "content,cost_error,expected",
    [
        ("  Reader answer\n", None, ("Reader answer", 0.125)),
        (None, None, ("", 0.125)),
        (
            "Reader answer",
            RuntimeError("Unknown cost"),
            ("Reader answer", 0.0),
        ),
    ],
)
def test_reader_response_and_cost(content, cost_error, expected):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    reader = QueryDocument(upload_id="test-upload", request="Summarize this")
    part = {"type": "text", "text": "Document content"}

    with (
        patch("litellm.completion", return_value=response) as completion,
        patch(
            "litellm.completion_cost",
            return_value=0.125,
            side_effect=cost_error,
        ) as completion_cost,
    ):
        assert reader.ask("notes.txt", part, "test-model") == expected

    completion.assert_called_once()
    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "test-model"
    assert kwargs["messages"][1] == {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": 'File: "notes.txt"\n\nRequest: Summarize this',
            },
            part,
        ],
    }
    completion_cost.assert_called_once_with(completion_response=response)
