"""The docassemble settings system check. DB-free.

A key without an API root beside it degrades every prefill to the plain
interview with only a per-request log line; the check makes that state a
deploy-time warning instead. The no-docassemble-at-all state is not the
check's business: the registry logs which flows lose the handoff there.
"""

import pytest
from django.test import override_settings

from litigant_portal.app.checks.docassemble import check_docassemble_settings


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
