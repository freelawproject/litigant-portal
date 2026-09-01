"""Tests for the thread endpoints in views/chat_engine.py, through the
assistant surface.

Every endpoint is a cross-identity ownership boundary: chat_thread_get scopes
by identity and thread_type, and a regression there means one litigant reading
another's conversation. All tests are postgres-marked (`make test`).
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from litigant_portal.app.models import ChatMessage, ChatThread, UserIdentity
from litigant_portal.app.services.chat_engine import chat_message_create
from litigant_portal.app.services.user import user_identity_ensure

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]

ASSISTANT_BASE = "/api/agents/assistant/"
MODEL = "gpt-5-mini"


def _client_identity():
    """A client with an established anonymous session and its identity."""
    client = Client()
    client.get(ASSISTANT_BASE + "threads/")
    identity = UserIdentity.objects.get(session_key=client.session.session_key)
    return client, identity


def _superuser_client_identity():
    # Identity for an authenticated user is keyed by user, not session key,
    # so login-time session rotation doesn't detach it.
    user = get_user_model().objects.create_superuser(
        username="root", password="pw"
    )
    client = Client()
    client.force_login(user)
    return client, user_identity_ensure(user=user)


def _thread(identity, thread_type="user_chat", **kwargs):
    return ChatThread.objects.create(
        identity=identity, thread_type=thread_type, **kwargs
    )


def _message(thread, content, role="user", **kwargs):
    return chat_message_create(
        thread_id=thread.id,
        data={"role": role, "content": content},
        model=MODEL,
        num_tokens=kwargs.pop("num_tokens", 0),
        **kwargs,
    )


# thread_list


def test_thread_list_excludes_other_identities_threads():
    client, identity = _client_identity()
    mine = _thread(identity)
    stranger = UserIdentity.objects.create(session_key="stranger")
    _thread(stranger)

    res = client.get(ASSISTANT_BASE + "threads/")

    assert res.status_code == 200
    assert [t["id"] for t in res.json()["threads"]] == [str(mine.id)]


def test_thread_list_excludes_other_thread_types():
    client, identity = _client_identity()
    _thread(identity, thread_type="weather_chat")

    assert client.get(ASSISTANT_BASE + "threads/").json()["threads"] == []


def test_thread_list_orders_by_most_recently_updated():
    client, identity = _client_identity()
    first = _thread(identity)
    _thread(identity)
    first.save()  # bumps updated_at

    ids = [
        t["id"]
        for t in client.get(ASSISTANT_BASE + "threads/").json()["threads"]
    ]

    assert ids[0] == str(first.id)


def test_thread_list_snippet_skips_hidden_and_meta_messages():
    client, identity = _client_identity()
    thread = _thread(identity)
    _message(thread, "visible answer", role="assistant")
    _message(thread, "injected context", hidden=True)
    _message(thread, "bookkeeping", meta=True)

    threads = client.get(ASSISTANT_BASE + "threads/").json()["threads"]

    assert threads[0]["snippet"] == "visible answer"


def test_thread_list_snippet_is_truncated_to_500_chars():
    client, identity = _client_identity()
    thread = _thread(identity)
    _message(thread, "x" * 600)

    threads = client.get(ASSISTANT_BASE + "threads/").json()["threads"]

    assert len(threads[0]["snippet"]) == 500


def test_thread_list_last_at_falls_back_to_updated_at_when_empty():
    client, identity = _client_identity()
    thread = _thread(identity)

    threads = client.get(ASSISTANT_BASE + "threads/").json()["threads"]

    assert threads[0]["last_at"] == thread.updated_at.isoformat()


# message_list


def test_message_list_returns_thread_payload():
    client, identity = _client_identity()
    thread = _thread(identity, description="my case")
    _message(thread, "hello")

    res = client.get(ASSISTANT_BASE + f"threads/{thread.id}/")

    assert res.status_code == 200
    payload = res.json()
    assert payload["id"] == str(thread.id)
    assert payload["description"] == "my case"
    assert payload["state"] == {}
    # Item contents are pinned by test_chat_hidden.py; here only the shape.
    assert isinstance(payload["items"], list)


def test_message_list_of_another_identitys_thread_is_404():
    client, _ = _client_identity()
    stranger = UserIdentity.objects.create(session_key="stranger")
    thread = _thread(stranger)

    res = client.get(ASSISTANT_BASE + f"threads/{thread.id}/")

    assert res.status_code == 404
    assert res.json()["error"] == "Thread not found"


def test_message_list_of_other_thread_type_is_404():
    client, identity = _client_identity()
    thread = _thread(identity, thread_type="weather_chat")

    assert (
        client.get(ASSISTANT_BASE + f"threads/{thread.id}/").status_code == 404
    )


def test_message_list_of_unknown_thread_is_404():
    client, _ = _client_identity()

    res = client.get(
        ASSISTANT_BASE + "threads/00000000-0000-0000-0000-000000000000/"
    )

    assert res.status_code == 404


# thread_usage


def test_thread_usage_is_forbidden_for_non_superuser():
    client, identity = _client_identity()
    thread = _thread(identity)

    res = client.get(ASSISTANT_BASE + f"threads/{thread.id}/usage/")

    assert res.status_code == 403
    assert res.json()["error"] == "Forbidden"


def test_thread_usage_sums_all_messages_including_hidden_and_meta():
    client, identity = _superuser_client_identity()
    thread = _thread(identity)
    _message(thread, "visible", num_tokens=10, cost=0.1)
    _message(thread, "hidden", num_tokens=20, cost=0.2, hidden=True)
    _message(thread, "meta", num_tokens=30, cost=0.3, meta=True)

    res = client.get(ASSISTANT_BASE + f"threads/{thread.id}/usage/")

    assert res.status_code == 200
    payload = res.json()
    assert payload["total_tokens"] == 60
    assert payload["total_cost"] == pytest.approx(0.6)


def test_thread_usage_of_empty_thread_is_zero():
    client, identity = _superuser_client_identity()
    thread = _thread(identity)

    payload = client.get(ASSISTANT_BASE + f"threads/{thread.id}/usage/").json()

    assert payload == {"total_tokens": 0, "total_cost": 0.0}


def test_thread_usage_of_another_identitys_thread_is_404():
    client, _ = _superuser_client_identity()
    stranger = UserIdentity.objects.create(session_key="stranger")
    thread = _thread(stranger)

    res = client.get(ASSISTANT_BASE + f"threads/{thread.id}/usage/")

    assert res.status_code == 404


# thread_delete


def test_thread_delete_removes_thread_and_cascades_messages():
    client, identity = _client_identity()
    thread = _thread(identity)
    _message(thread, "hello")

    res = client.post(ASSISTANT_BASE + f"threads/{thread.id}/delete/")

    assert res.status_code == 200
    assert res.json() == {"deleted": True}
    assert not ChatThread.objects.filter(id=thread.id).exists()
    # Cascade is current behavior; the audit-log retention work (#745) will
    # need to revisit this — the assertion is here to make that change loud.
    assert not ChatMessage.objects.filter(thread_id=thread.id).exists()


def test_thread_delete_of_another_identitys_thread_is_404_and_kept():
    client, _ = _client_identity()
    stranger = UserIdentity.objects.create(session_key="stranger")
    thread = _thread(stranger)

    res = client.post(ASSISTANT_BASE + f"threads/{thread.id}/delete/")

    assert res.status_code == 404
    assert ChatThread.objects.filter(id=thread.id).exists()


def test_thread_delete_of_other_thread_type_is_404_and_kept():
    client, identity = _client_identity()
    thread = _thread(identity, thread_type="weather_chat")

    res = client.post(ASSISTANT_BASE + f"threads/{thread.id}/delete/")

    assert res.status_code == 404
    assert ChatThread.objects.filter(id=thread.id).exists()
