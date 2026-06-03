"""AnswerStore tests — session-backed fact_gather answers, namespaced per flow.

AnswerStore needs only a Django session (a mutable mapping that tracks
``.modified``). We exercise it against the ``signed_cookies`` backend so these
tests stay DB-free and run in the fast suite; the contract is identical across
session backends.
"""

import json

from django.contrib.sessions.backends.signed_cookies import SessionStore

from litigant_portal.app.topic_flow.answer_store import AnswerStore

FLOW = ("north-dakota", "adult_name_change", "petitioner")
FLOW_KEY = "north-dakota/adult_name_change/petitioner"


def _store(session=None, flow=FLOW):
    return AnswerStore(
        session if session is not None else SessionStore(), *flow
    )


# --- read / write -----------------------------------------------------------


def test_set_then_get_roundtrips():
    store = _store()
    store.set("pubdate", "2026-05-01")
    assert store.get("pubdate") == "2026-05-01"


def test_get_absent_returns_none():
    # Absent answer is the common case (guest hasn't filled the form) — None,
    # never KeyError; the deadline layer reads this as "not yet answered".
    assert _store().get("pubdate") is None


def test_all_returns_this_flows_answers():
    store = _store()
    store.update({"name": "Sandra", "pubdate": "2026-05-01"})
    assert store.all() == {"name": "Sandra", "pubdate": "2026-05-01"}


def test_all_empty_when_nothing_stored():
    assert _store().all() == {}


# --- update merges, last-write-wins -----------------------------------------


def test_update_merges_without_wiping_prior_answers():
    store = _store()
    store.set("name", "Sandra")
    store.update({"pubdate": "2026-05-01", "dob": "1990-02-03"})
    assert store.all() == {
        "name": "Sandra",
        "pubdate": "2026-05-01",
        "dob": "1990-02-03",
    }


def test_update_overwrites_same_question_last_write_wins():
    store = _store()
    store.set("pubdate", "2026-05-01")
    store.update({"pubdate": "2026-06-09"})
    assert store.get("pubdate") == "2026-06-09"


# --- clear ------------------------------------------------------------------


def test_clear_empties_only_this_flow():
    session = SessionStore()
    petitioner = _store(
        session, ("north-dakota", "adult_name_change", "petitioner")
    )
    respondent = _store(
        session, ("north-dakota", "adult_name_change", "respondent")
    )
    petitioner.set("name", "Sandra")
    respondent.set("name", "Pat")
    petitioner.clear()
    assert petitioner.all() == {}
    assert respondent.get("name") == "Pat"


# --- flow isolation ---------------------------------------------------------


def test_flows_are_isolated_within_one_session():
    session = SessionStore()
    petitioner = _store(
        session, ("north-dakota", "adult_name_change", "petitioner")
    )
    respondent = _store(
        session, ("north-dakota", "adult_name_change", "respondent")
    )
    petitioner.set("name", "Sandra")
    assert respondent.get("name") is None
    respondent.set("name", "Pat")
    assert petitioner.get("name") == "Sandra"
    assert respondent.get("name") == "Pat"


# --- session.modified (Django doesn't detect deep-dict mutation) ------------


def test_set_marks_session_modified():
    session = SessionStore()
    session.modified = False
    _store(session).set("pubdate", "2026-05-01")
    assert session.modified is True


def test_update_marks_session_modified():
    session = SessionStore()
    session.modified = False
    _store(session).update({"pubdate": "2026-05-01"})
    assert session.modified is True


def test_clear_marks_session_modified():
    session = SessionStore()
    store = _store(session)
    store.set("pubdate", "2026-05-01")
    session.modified = False
    store.clear()
    assert session.modified is True


# --- storage layout / serialization -----------------------------------------


def test_payload_is_namespaced_under_single_key_and_json_serializable():
    session = SessionStore()
    _store(session).set("pubdate", "2026-05-01")
    payload = session[AnswerStore.SESSION_KEY]
    # One top-level key; the flow lives under a flat composite *string* key.
    assert list(payload) == [FLOW_KEY]
    assert payload[FLOW_KEY] == {"pubdate": "2026-05-01"}
    # The session serializes to JSON between requests; assert the payload
    # survives a full round-trip unchanged, not merely that it doesn't raise.
    assert json.loads(json.dumps(payload)) == payload


def test_values_stored_raw_not_coerced():
    # Dumb storage: a date answer stays the raw POST string. Parsing/typing
    # is the deadline layer's job; validation is upstream at corpus load.
    store = _store()
    store.set("pubdate", "2026-05-01")
    value = store.get("pubdate")
    assert value == "2026-05-01"
    assert isinstance(value, str)
