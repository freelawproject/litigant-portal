"""docassemble client tests: the three-call session handoff, with HTTP mocked.

DB-free. ``requests.request`` is replaced per test, so these assert the exact
calls the client makes: payload shapes, the one-time resume flag, the API key
in a header, and no answer ever reaching a URL.
"""

import pytest
import requests
from django.test import override_settings

from litigant_portal.app.services.docassemble import (
    DocassembleError,
    docassemble_session_create,
)

INTERVIEW = "docassemble.playground1:petition-standard.yml"
INTERVIEW_URL = f"https://qa.example.gov/interview/interview?i={INTERVIEW}"
RESUME = "https://qa.example.gov/interview/session?resume=abc"
VARIABLES = {"current_first": "Sandra", "residence_county": "Burleigh"}


class _Response:
    def __init__(self, payload=None, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


class _Recorder:
    """Stands in for ``requests.request``, replying down a scripted list."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        reply = self.responses.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def _happy_path():
    return _Recorder(
        _Response({"session": "sess-1"}),
        _Response(status=204),
        _Response({"url": RESUME}),
    )


@pytest.fixture
def recorder(monkeypatch):
    recording = _happy_path()
    monkeypatch.setattr(requests, "request", recording)
    return recording


def _create(**kwargs):
    return docassemble_session_create(
        interview_url=kwargs.pop("interview_url", INTERVIEW_URL),
        variables=kwargs.pop("variables", VARIABLES),
    )


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_returns_the_resume_url(recorder):
    assert _create() == RESUME


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_calls_the_three_endpoints_in_order(recorder):
    _create()
    assert [(c["method"], c["url"]) for c in recorder.calls] == [
        ("GET", "https://qa.example.gov/interview/api/session/new"),
        ("POST", "https://qa.example.gov/interview/api/session"),
        ("POST", "https://qa.example.gov/interview/api/resume_url"),
    ]


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_new_session_asks_for_the_interview_from_the_launch_url(recorder):
    _create()
    assert recorder.calls[0]["params"] == {"i": INTERVIEW}


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_variables_post_carries_the_session_and_skips_evaluation(recorder):
    _create()
    assert recorder.calls[1]["json"] == {
        "i": INTERVIEW,
        "session": "sess-1",
        "variables": VARIABLES,
        "question": 0,
    }


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_resume_url_is_requested_one_time_and_expiring(recorder):
    _create()
    payload = recorder.calls[2]["json"]
    assert payload["one_time"] == 1
    assert 0 < payload["expire"] <= 3600


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_api_key_travels_in_a_header_on_every_call(recorder):
    _create()
    assert all(c["headers"]["X-API-Key"] == "k" for c in recorder.calls)
    assert not any("k" in c["url"] for c in recorder.calls)


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_no_answer_value_reaches_a_url(recorder):
    # The whole point of POSTing the payload: PII stays out of URLs, which
    # land in access logs, browser history and Referer headers.
    _create()
    for call in recorder.calls:
        for value in VARIABLES.values():
            assert value not in call["url"]
            assert value not in str(call.get("params") or "")


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_every_call_sets_a_timeout(recorder):
    _create()
    assert all(c["timeout"] for c in recorder.calls)


@override_settings(
    DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL="http://localhost:8100"
)
def test_base_url_override_replaces_the_api_root(recorder):
    _create()
    assert all(
        c["url"].startswith("http://localhost:8100/api/")
        for c in recorder.calls
    )


@override_settings(DOCASSEMBLE_API_KEY=None, DOCASSEMBLE_BASE_URL=None)
def test_missing_api_key_raises_without_calling_out(recorder):
    with pytest.raises(DocassembleError):
        _create()
    assert recorder.calls == []


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_launch_url_without_an_interview_reference_raises(recorder):
    with pytest.raises(DocassembleError):
        _create(interview_url="https://qa.example.gov/interview/interview")
    assert recorder.calls == []


@pytest.mark.parametrize(
    "failure",
    [
        _Response(status=403),
        _Response(status=500),
        requests.Timeout("timed out"),
        requests.ConnectionError("refused"),
    ],
    ids=["forbidden", "server-error", "timeout", "connection-refused"],
)
@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_a_failed_first_call_raises_docassemble_error(monkeypatch, failure):
    monkeypatch.setattr(requests, "request", _Recorder(failure))
    with pytest.raises(DocassembleError):
        _create()


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_a_failed_variables_post_raises_docassemble_error(monkeypatch):
    monkeypatch.setattr(
        requests,
        "request",
        _Recorder(
            _Response({"session": "sess-1"}),
            _Response(status=400),
            _Response(status=204),
        ),
    )
    with pytest.raises(DocassembleError):
        _create()


# --- orphan cleanup ----------------------------------------------------------
# A session that fails past creation already holds the litigant's answers, and
# nothing will ever resume it (#805 covers only downloaded packets), so the
# client deletes it on the way out.


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_a_failed_variables_post_deletes_the_orphaned_session(monkeypatch):
    recorder = _Recorder(
        _Response({"session": "sess-1"}),
        _Response(status=400),
        _Response(status=204),
    )
    monkeypatch.setattr(requests, "request", recorder)
    with pytest.raises(DocassembleError):
        _create()
    cleanup = recorder.calls[-1]
    assert cleanup["method"] == "DELETE"
    assert cleanup["url"] == "https://qa.example.gov/interview/api/session"
    assert cleanup["params"] == {"i": INTERVIEW, "session": "sess-1"}


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_a_failed_resume_url_deletes_the_orphaned_session(monkeypatch):
    recorder = _Recorder(
        _Response({"session": "sess-1"}),
        _Response(status=204),
        requests.Timeout("timed out"),
        _Response(status=204),
    )
    monkeypatch.setattr(requests, "request", recorder)
    with pytest.raises(DocassembleError):
        _create()
    assert recorder.calls[-1]["method"] == "DELETE"


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_a_failed_cleanup_does_not_mask_the_original_error(monkeypatch):
    monkeypatch.setattr(
        requests,
        "request",
        _Recorder(
            _Response({"session": "sess-1"}),
            _Response(status=204),
            _Response(status=500),
            requests.ConnectionError("refused"),
        ),
    )
    with pytest.raises(DocassembleError, match="resume_url"):
        _create()


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_the_happy_path_never_deletes(recorder):
    _create()
    assert not any(c["method"] == "DELETE" for c in recorder.calls)


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_a_session_response_without_a_session_raises(monkeypatch):
    monkeypatch.setattr(requests, "request", _Recorder(_Response({})))
    with pytest.raises(DocassembleError):
        _create()


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_a_resume_response_without_a_url_raises(monkeypatch):
    monkeypatch.setattr(
        requests,
        "request",
        _Recorder(
            _Response({"session": "sess-1"}),
            _Response(status=204),
            _Response({}),
            _Response(status=204),
        ),
    )
    with pytest.raises(DocassembleError):
        _create()


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_a_bare_string_resume_response_is_accepted(monkeypatch):
    monkeypatch.setattr(
        requests,
        "request",
        _Recorder(
            _Response({"session": "sess-1"}),
            _Response(status=204),
            _Response(RESUME),
        ),
    )
    assert _create() == RESUME


@override_settings(DOCASSEMBLE_API_KEY="k", DOCASSEMBLE_BASE_URL=None)
def test_an_empty_variables_dict_still_creates_a_session(recorder):
    assert _create(variables={}) == RESUME
    assert recorder.calls[1]["json"]["variables"] == {}


@override_settings(
    DOCASSEMBLE_API_KEY="k",
    DOCASSEMBLE_BASE_URL="http://docassemble",
    DOCASSEMBLE_PUBLIC_URL="https://qa.example.gov/interview",
)
def test_resume_url_is_rewritten_onto_the_public_origin(monkeypatch):
    # docassemble builds the launch URL from the host we called it on, which
    # on a deployment is internal and unreachable from a browser.
    monkeypatch.setattr(
        requests,
        "request",
        _Recorder(
            _Response({"session": "sess-1"}),
            _Response(status=204),
            _Response({"url": "http://docassemble/launch?c=tok"}),
        ),
    )
    assert _create() == "https://qa.example.gov/launch?c=tok"


@override_settings(
    DOCASSEMBLE_API_KEY="k",
    DOCASSEMBLE_BASE_URL=None,
    DOCASSEMBLE_PUBLIC_URL=None,
)
def test_resume_url_is_left_alone_without_a_public_origin(recorder):
    assert _create() == RESUME
