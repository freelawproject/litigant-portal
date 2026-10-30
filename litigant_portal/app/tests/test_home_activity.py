"""Tests for the home page's server-rendered Activity list.

The chat page's thread list is Alpine-rendered from the API, so the home
page gets its own static render of the same rows (views/utils.py
activity_threads). All tests are postgres-marked (`make test`).
"""

import re

import pytest
from django.test import Client
from django.urls import reverse

from litigant_portal.app.models import ChatThread, UserIdentity
from litigant_portal.app.services.chat_engine import chat_message_create

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

ASSISTANT_BASE = "/api/agents/assistant/"


def _client_identity():
    """A client with an established anonymous session and its identity."""
    client = Client()
    client.get(ASSISTANT_BASE + "threads/")
    identity = UserIdentity.objects.get(session_key=client.session.session_key)
    return client, identity


def _thread(identity, **kwargs):
    return ChatThread.objects.create(
        identity=identity, thread_type="user_chat", **kwargs
    )


def _message(thread, content, role="user"):
    return chat_message_create(
        thread_id=thread.id,
        data={"role": role, "content": content},
        model="gpt-5-mini",
        num_tokens=0,
    )


def _left_region(html):
    match = re.search(r'<aside id="frame-left".*?</aside>', html, re.S)
    assert match, "page has no left region"
    return match.group(0)


def test_home_left_region_lists_the_visitors_threads_as_chat_deep_links():
    client, identity = _client_identity()
    thread = _thread(identity, description="Name change")
    _message(thread, "hi need help with north dakota")

    left = _left_region(client.get(reverse("pages:home")).content.decode())

    assert f"?thread={thread.id}" in left
    assert "Name change" in left
    assert "hi need help with north dakota" in left
    assert "Your chats will show here." not in left
    # The empty state's "Start a chat" is gone with it, so the list
    # carries its own.
    assert "Start a chat" in left
    assert f'href="{reverse("pages:chat")}"' in left
    # Matches the chat sidebar's timeSince(), where timesince alone
    # would say "0 minutes ago".
    assert "just now" in left
    assert "0 minutes" not in left


def test_home_left_region_titles_an_undescribed_thread_new_chat():
    client, identity = _client_identity()
    _thread(identity, description="")

    left = _left_region(client.get(reverse("pages:home")).content.decode())

    assert "New chat" in left


def test_home_left_region_excludes_other_identities_threads():
    client, _ = _client_identity()
    stranger = UserIdentity.objects.create(session_key="stranger")
    other = _thread(stranger, description="Not yours")

    left = _left_region(client.get(reverse("pages:home")).content.decode())

    assert "Not yours" not in left
    assert f"{other.id}" not in left
    assert "Your chats will show here." in left


def test_home_keeps_the_empty_state_and_mints_no_identity_for_a_fresh_visitor():
    # An unguarded request.identity read banks a UserIdentity row per
    # anonymous hit, crawlers included (views/utils.py has_identity).
    left = _left_region(Client().get(reverse("pages:home")).content.decode())

    assert "Your chats will show here." in left
    assert not UserIdentity.objects.exists()
