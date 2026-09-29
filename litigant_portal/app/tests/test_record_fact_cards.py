"""Postgres tests: the RecordFact result card, rendered through the thread
history endpoint.

History and the live stream render the same template with the same
``{"data": render_data or {}}`` context, so these cover both. The literal
``render_data`` dicts without an ``unchanged`` key are the shape stored by
threads written before that key existed; they must keep rendering.
"""

import json

import pytest
from django.test import Client

from litigant_portal.agents.tools.record_fact import RecordFact
from litigant_portal.app.models import ChatThread, UserIdentity, Variable
from litigant_portal.app.services.chat_engine import chat_message_create
from litigant_portal.app.services.topic_flow import variable_answer_set

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

ASSISTANT_BASE = "/api/agents/assistant/"
MODEL = "gpt-5-mini"

SAVED_TITLE = "Saved to your answers"
UNCHANGED_TITLE = "Already in your answers"
FAILED_TITLE = "Could not save your answers"
CRASHED = "Something went wrong"
REVIEW_NOTE = "You will review and confirm these"

SAVED = [
    {"name": "county", "label": "County", "value": "Cass", "cleared": False}
]
UNCHANGED = [
    {
        "name": "date_of_birth",
        "label": "Date of birth",
        "value": "Thursday, January 31, 1991",
    }
]
ERRORS = [{"name": "zip", "label": "ZIP code", "message": "must be a string"}]


@pytest.fixture
def client_thread():
    client = Client()
    client.get(ASSISTANT_BASE + "threads/")
    identity = UserIdentity.objects.get(session_key=client.session.session_key)
    thread = ChatThread.objects.create(
        identity=identity, thread_type="user_chat"
    )
    return client, thread


def _card_html(client, thread, *, facts, render_data):
    chat_message_create(
        thread_id=thread.id,
        data={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "RecordFact",
                        "arguments": json.dumps({"facts": facts}),
                    },
                }
            ],
        },
        model=MODEL,
        num_tokens=0,
    )
    tool_msg = {
        "role": "tool",
        "tool_call_id": "call_1",
        "name": "RecordFact",
        "content": "",
    }
    if render_data is not None:
        tool_msg["data"] = render_data
    chat_message_create(
        thread_id=thread.id, data=tool_msg, model=MODEL, num_tokens=0
    )

    items = client.get(ASSISTANT_BASE + f"threads/{thread.id}/").json()[
        "items"
    ]
    (card,) = [item for item in items if item.get("name") == "RecordFact"]
    return card["result_render_html"]


@pytest.mark.parametrize(
    ("render_data", "title", "shown", "hidden"),
    [
        (
            {"saved": [], "unchanged": UNCHANGED, "errors": []},
            UNCHANGED_TITLE,
            ["Date of birth", "Thursday, January 31, 1991"],
            [FAILED_TITLE, CRASHED, REVIEW_NOTE, "Not saved"],
        ),
        (
            {"saved": SAVED, "unchanged": UNCHANGED, "errors": []},
            SAVED_TITLE,
            ["Cass", "Thursday, January 31, 1991", REVIEW_NOTE],
            [UNCHANGED_TITLE, FAILED_TITLE, "Not saved"],
        ),
        (
            {"saved": [], "unchanged": UNCHANGED, "errors": ERRORS},
            UNCHANGED_TITLE,
            ["Thursday, January 31, 1991", "Not saved", "ZIP code"],
            [FAILED_TITLE, CRASHED, REVIEW_NOTE],
        ),
        (
            {"saved": SAVED, "unchanged": UNCHANGED, "errors": ERRORS},
            SAVED_TITLE,
            ["Cass", "Thursday, January 31, 1991", "Not saved", REVIEW_NOTE],
            [UNCHANGED_TITLE, FAILED_TITLE],
        ),
        (
            {"saved": SAVED, "errors": []},
            SAVED_TITLE,
            ["Cass", REVIEW_NOTE],
            [UNCHANGED_TITLE, FAILED_TITLE],
        ),
        (
            {"saved": [], "errors": ERRORS},
            FAILED_TITLE,
            ["Not saved", "ZIP code: must be a string"],
            [SAVED_TITLE, UNCHANGED_TITLE, CRASHED, REVIEW_NOTE],
        ),
        (
            None,
            FAILED_TITLE,
            [CRASHED],
            [SAVED_TITLE, UNCHANGED_TITLE, REVIEW_NOTE],
        ),
    ],
    ids=[
        "unchanged-only-is-success",
        "saved-and-unchanged",
        "unchanged-and-error-is-not-failure",
        "saved-unchanged-and-error",
        "saved-only-legacy-shape",
        "errors-only-legacy-shape",
        "tool-crashed-no-data",
    ],
)
def test_result_card_title_and_body(
    client_thread, render_data, title, shown, hidden
):
    client, thread = client_thread

    html = _card_html(
        client, thread, facts={"county": "cass"}, render_data=render_data
    )

    assert title in html
    for text in shown:
        assert text in html
    for text in hidden:
        assert text not in html


def test_restated_confirmed_fact_renders_as_already_saved(client_thread):
    client, thread = client_thread
    county = Variable.objects.create(name="county", label="County")
    variable_answer_set(
        identity=thread.identity,
        variable=county,
        value="Cass",
        reviewed=True,
    )
    output = RecordFact(facts={"county": "Cass"})(thread_id=thread.id)

    html = _card_html(
        client,
        thread,
        facts={"county": "Cass"},
        render_data=output.render_data,
    )

    assert UNCHANGED_TITLE in html
    assert "Cass" in html
    assert FAILED_TITLE not in html
