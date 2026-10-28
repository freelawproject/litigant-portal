"""The docassemble settings system checks. DB-free.

A key without an API root beside it degrades every prefill to the plain
interview with only a per-request log line; W001 makes that state a
deploy-time warning instead. W002 covers the no-docassemble-at-all state:
it names the corpus flows whose interview handoff is hidden, at deploy time
rather than lazily on the first request.
"""

import pytest
from django.test import override_settings

from litigant_portal.app.checks import docassemble as docassemble_checks
from litigant_portal.app.checks.docassemble import (
    check_docassemble_settings,
    check_unservable_handoffs,
)
from litigant_portal.app.selectors.corpus import FlowSchema

STANDARD = ("north-dakota", "adult-name-change", "standard")
WAIVER = ("north-dakota", "adult-name-change", "waiver")

NO_DOCASSEMBLE = override_settings(
    DOCASSEMBLE_API_KEY=None,
    DOCASSEMBLE_BASE_URL=None,
    DOCASSEMBLE_PUBLIC_URL=None,
)


def _flow(handoff=True):
    return FlowSchema.model_validate(
        {
            "name": "F",
            "sections": [{"id": "s", "heading": "H", "content": "C"}],
            "handoff": (
                {"interview_reference": "docassemble.pkg:data/questions/p.yml"}
                if handoff
                else None
            ),
        }
    )


def _corpus(monkeypatch, flows):
    """The corpus flows the check reads: ``{(court, topic, role):
    FlowSchema}``, or a callable that raises."""
    load = flows if callable(flows) else lambda: dict(flows)
    monkeypatch.setattr(docassemble_checks, "corpus_load_flows", load)


# --- W001: a key without its API root ---------------------------------------


@override_settings(
    DOCASSEMBLE_API_KEY="k",
    DOCASSEMBLE_BASE_URL=None,
    DOCASSEMBLE_PUBLIC_URL=None,
)
def test_a_key_without_a_base_url_warns():
    warnings = check_docassemble_settings(None)
    assert [w.id for w in warnings] == ["docassemble.W001"]


@override_settings(
    DOCASSEMBLE_API_KEY="k",
    DOCASSEMBLE_BASE_URL=None,
    DOCASSEMBLE_PUBLIC_URL="https://qa.example.gov/interview",
)
def test_a_public_url_does_not_silence_the_warning():
    # The public base serves the launch link, never the API: with it set the
    # button renders, so this is exactly the state where litigants quietly
    # get unprefilled interviews.
    warnings = check_docassemble_settings(None)
    assert [w.id for w in warnings] == ["docassemble.W001"]


@pytest.mark.parametrize(
    ("api_key", "base_url"),
    [
        ("k", "http://localhost:8100"),
        (None, "http://localhost:8100"),
        (None, None),
    ],
    ids=["fully-configured", "no-key", "no-docassemble-at-all"],
)
def test_coherent_settings_pass(api_key, base_url):
    with override_settings(
        DOCASSEMBLE_API_KEY=api_key,
        DOCASSEMBLE_BASE_URL=base_url,
        DOCASSEMBLE_PUBLIC_URL=None,
    ):
        assert check_docassemble_settings(None) == []


# --- W002: handoffs no docassemble serves -----------------------------------


@NO_DOCASSEMBLE
def test_a_handoff_without_docassemble_warns_naming_the_flow(monkeypatch):
    _corpus(monkeypatch, {STANDARD: _flow(), WAIVER: _flow(handoff=False)})
    warnings = check_unservable_handoffs(None)
    assert [w.id for w in warnings] == ["docassemble.W002"]
    assert "north-dakota/adult-name-change/standard" in warnings[0].msg
    assert "waiver" not in warnings[0].msg


@NO_DOCASSEMBLE
def test_flows_without_handoffs_stay_quiet_without_docassemble(monkeypatch):
    _corpus(monkeypatch, {STANDARD: _flow(handoff=False)})
    assert check_unservable_handoffs(None) == []


@pytest.mark.parametrize(
    ("base_url", "public_url"),
    [
        ("http://localhost:8100", None),
        (None, "https://qa.example.gov/interview"),
    ],
    ids=["api-base-serves-the-link", "public-base-serves-the-link"],
)
def test_a_configured_docassemble_silences_the_handoff_warning(
    monkeypatch, base_url, public_url
):
    _corpus(monkeypatch, {STANDARD: _flow()})
    with override_settings(
        DOCASSEMBLE_API_KEY=None,
        DOCASSEMBLE_BASE_URL=base_url,
        DOCASSEMBLE_PUBLIC_URL=public_url,
    ):
        assert check_unservable_handoffs(None) == []


@NO_DOCASSEMBLE
def test_an_unparseable_corpus_flow_is_left_to_the_corpus_check(monkeypatch):
    # corpus.E001 already reports it; this check must not crash on it.
    def broken():
        raise ValueError("flows/standard.yml: cannot load")

    _corpus(monkeypatch, broken)
    assert check_unservable_handoffs(None) == []
