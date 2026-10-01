"""Postgres tests: the ReviewFacts result card, rendered through the thread
history endpoint.

History and the live stream render the same template with the same
``{"data": render_data or {}}`` context, so these cover both.
"""

import re

import pytest
from django.test import Client

from litigant_portal.app.models import ChatThread, UserIdentity
from litigant_portal.app.services.chat_engine import chat_message_create

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

ASSISTANT_BASE = "/api/agents/assistant/"
MODEL = "gpt-5-mini"

TITLE = "Review your answers"
CRASHED = "Could not prepare your answers"
CONFIRM = "Confirm my answers"
LAUNCH = "Fill out your forms"
GUIDE = "open the guide"
INTERVIEW_URL = "/t/test-court/name-change/standard/interview/"
GUIDE_URL = "/t/test-court/name-change/standard/"

FACTS = [
    {
        "name": "first_name",
        "label": "First name",
        "value": "Sandra",
        "reviewed": True,
    },
    {"name": "county", "label": "County", "value": "Cass", "reviewed": False},
]
TRACK = {"court": "test-court", "topic": "name-change", "role": "standard"}
AS_OF = "2026-09-29T12:00:00.000000+00:00"


def _data(**overrides):
    data = {
        "facts": FACTS,
        "missing": [],
        "confirm_names": ["first_name", "county"],
        "as_of": AS_OF,
        "all_reviewed": False,
        "interview_available": True,
        **TRACK,
    }
    data.update(overrides)
    return data


@pytest.fixture
def client_thread():
    client = Client()
    client.get(ASSISTANT_BASE + "threads/")
    identity = UserIdentity.objects.get(session_key=client.session.session_key)
    thread = ChatThread.objects.create(
        identity=identity, thread_type="user_chat"
    )
    return client, thread


def _card_html(client, thread, *, render_data):
    chat_message_create(
        thread_id=thread.id,
        data={
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "ReviewFacts", "arguments": "{}"},
                }
            ],
        },
        model=MODEL,
        num_tokens=0,
    )
    tool_msg = {
        "role": "tool",
        "tool_call_id": "call_1",
        "name": "ReviewFacts",
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
    (card,) = [item for item in items if item.get("name") == "ReviewFacts"]
    return card["result_render_html"]


def _badges(html):
    """``[(role, hidden)]`` for every badge in the card, in order."""
    return [
        (m.group(1), "hidden" in m.group(2))
        for m in re.finditer(r'data-role="(badge-\w+)"([^>]*)>', html)
    ]


def test_facts_render_with_label_value_and_review_badge(client_thread):
    html = _card_html(*client_thread, render_data=_data())
    assert TITLE in html
    assert "First name" in html and "Sandra" in html
    assert "County" in html and "Cass" in html
    # Both badges render per fact so the component can flip them on
    # confirm; only the one matching the stored state is visible.
    assert _badges(html) == [
        ("badge-confirmed", False),
        ("badge-pending", True),
        ("badge-confirmed", True),
        ("badge-pending", False),
    ]
    assert 'data-names="first_name,county"' in html
    assert f'data-as-of="{AS_OF}"' in html
    assert 'data-all-reviewed="false"' in html
    assert 'data-confirm-url="/facts/confirm/"' in html
    assert CONFIRM in html


def test_the_outcome_notes_render_hidden_for_the_component_to_reveal(
    client_thread,
):
    html = _card_html(*client_thread, render_data=_data())
    notes = {
        m.group(2): "hidden" in m.group(1) + m.group(3)
        for m in re.finditer(r'<p([^>]*)data-role="(\w+-note)"([^>]*)>', html)
    }
    assert notes == {
        "confirmed-note": True,
        "error-note": True,
        "stale-note": True,
    }
    # Revealing a note flips `hidden`, which a screen reader only announces
    # inside a live region (WCAG 4.1.3). One region wraps all three.
    (region,) = re.findall(
        r'<div aria-live="polite">(.*?)</div>', html, flags=re.DOTALL
    )
    assert region.count("-note") == 3


def test_missing_facts_are_listed_as_still_needed(client_thread):
    html = _card_html(
        *client_thread,
        render_data=_data(
            facts=[],
            confirm_names=[],
            missing=[{"name": "county", "label": "County"}],
        ),
    )
    assert "Still needed" in html and "County" in html
    assert CONFIRM not in html
    assert LAUNCH not in html


def test_launch_form_posts_to_the_interview_when_available(client_thread):
    html = _card_html(*client_thread, render_data=_data())
    assert LAUNCH in html
    assert f'action="{INTERVIEW_URL}"' in html
    assert GUIDE not in html


def test_guided_page_is_offered_when_no_interview_is_available(
    client_thread,
):
    html = _card_html(
        *client_thread, render_data=_data(interview_available=False)
    )
    assert LAUNCH not in html
    assert GUIDE in html
    assert f'href="{GUIDE_URL}"' in html


def test_no_next_step_is_offered_without_a_registry_page(client_thread):
    html = _card_html(
        *client_thread,
        render_data=_data(
            interview_available=False, court=None, topic=None, role=None
        ),
    )
    assert LAUNCH not in html
    assert GUIDE not in html
    assert CONFIRM in html


def test_the_card_never_renders_an_empty_csrf_input(client_thread):
    # An empty token input ahead of the page's real one would shadow it for
    # every chat POST; factReviewCard creates it filled instead.
    html = _card_html(*client_thread, render_data=_data())
    assert not re.search(r"name=.csrfmiddlewaretoken", html)


def test_all_reviewed_is_passed_to_the_component(client_thread):
    reviewed = [dict(f, reviewed=True) for f in FACTS]
    html = _card_html(
        *client_thread, render_data=_data(facts=reviewed, all_reviewed=True)
    )
    assert 'data-all-reviewed="true"' in html
    assert all(
        hidden for role, hidden in _badges(html) if role == "badge-pending"
    )


def test_a_tool_error_renders_the_failure_state(client_thread):
    html = _card_html(*client_thread, render_data=None)
    assert CRASHED in html
    assert TITLE not in html
    assert CONFIRM not in html
