"""The docassemble settings system checks. DB-free.

A key without an API root beside it degrades every prefill to the plain
interview with only a per-request log line; W001 makes that state a
deploy-time warning instead. W002 covers the no-docassemble-at-all state:
it names the flows whose interview handoff is hidden, at deploy time rather
than lazily on the first request that loads the registry.
"""

from pathlib import Path

import pytest
from django.test import override_settings

from litigant_portal.app.checks import docassemble as docassemble_checks
from litigant_portal.app.checks.docassemble import (
    check_docassemble_settings,
    check_unservable_handoffs,
)

FIXTURE = Path(__file__).resolve().parents[2] / "content" / "_test_fixture.yml"
VALID = FIXTURE.read_text(encoding="utf-8")
# The fixture with its packet opting into the interview handoff.
HANDOFF = VALID.replace(
    "id: filing_packet",
    "id: filing_packet\n    interview_reference: "
    "'docassemble.pkg:data/questions/p.yml'",
)


def _corpus(tmp_path, monkeypatch, text):
    flow = tmp_path / "flow.yml"
    flow.write_text(text)
    monkeypatch.setattr(
        docassemble_checks, "iter_corpus_paths", lambda _dir: [flow]
    )


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


@override_settings(
    DOCASSEMBLE_API_KEY=None,
    DOCASSEMBLE_BASE_URL=None,
    DOCASSEMBLE_PUBLIC_URL=None,
)
def test_a_handoff_without_docassemble_warns_naming_the_flow(
    tmp_path, monkeypatch
):
    _corpus(tmp_path, monkeypatch, HANDOFF)
    warnings = check_unservable_handoffs(None)
    assert [w.id for w in warnings] == ["docassemble.W002"]
    assert "test-court/test_topic/petitioner" in warnings[0].msg


@override_settings(
    DOCASSEMBLE_API_KEY=None,
    DOCASSEMBLE_BASE_URL=None,
    DOCASSEMBLE_PUBLIC_URL=None,
)
def test_flows_without_handoffs_stay_quiet_without_docassemble(
    tmp_path, monkeypatch
):
    _corpus(tmp_path, monkeypatch, VALID)
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
    tmp_path, monkeypatch, base_url, public_url
):
    _corpus(tmp_path, monkeypatch, HANDOFF)
    with override_settings(
        DOCASSEMBLE_API_KEY=None,
        DOCASSEMBLE_BASE_URL=base_url,
        DOCASSEMBLE_PUBLIC_URL=public_url,
    ):
        assert check_unservable_handoffs(None) == []


@override_settings(
    DOCASSEMBLE_API_KEY=None,
    DOCASSEMBLE_BASE_URL=None,
    DOCASSEMBLE_PUBLIC_URL=None,
)
def test_an_invalid_corpus_is_left_to_the_corpus_check(tmp_path, monkeypatch):
    # topic_flow.E001 already reports it; this check must not crash on it.
    _corpus(
        tmp_path,
        monkeypatch,
        "metadata: {court: c, topic: t, role: r, title: T}\nsections: []\n",
    )
    assert check_unservable_handoffs(None) == []
