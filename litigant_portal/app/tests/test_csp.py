"""Tests for the Content Security Policy header and its report endpoint.

The settings and report endpoint tests are DB-free; the home page header
test is postgres-marked.
"""

import json
import os
import runpy
from unittest import mock

import pytest
from django.urls import reverse
from django.utils.csp import CSP

import litigant_portal.settings
from litigant_portal.lp_logger import EVENTS

PUBLIC_BUCKET = "https://litigantportal-storage.s3.amazonaws.com"
PRIVATE_BUCKET = "https://litigantportal-private-storage.s3.amazonaws.com"


def _settings(environ):
    environ = {"SECRET_KEY": "test-secret-key", **environ}
    with mock.patch.dict(os.environ, environ, clear=True):
        return runpy.run_path(litigant_portal.settings.__file__)


@pytest.mark.parametrize(
    "environ",
    [{}, {"CSP_ENFORCED": "false"}],
    ids=["unset", "false"],
)
def test_policy_is_report_only_unless_enforced(environ):
    config = _settings(environ)

    assert config["SECURE_CSP_REPORT_ONLY"]["default-src"] == [CSP.SELF]
    assert "SECURE_CSP" not in config


def test_csp_enforced_moves_the_policy_to_the_enforcing_setting():
    config = _settings({"CSP_ENFORCED": "true"})

    assert config["SECURE_CSP"]["default-src"] == [CSP.SELF]
    assert "SECURE_CSP_REPORT_ONLY" not in config


@pytest.mark.parametrize(
    "environ",
    [{"DEBUG": "true", "USE_S3": "true"}, {"DEBUG": "false"}],
    ids=["debug-on-with-s3", "debug-off-default"],
)
def test_policy_allows_the_s3_origins_when_storage_is_s3(environ):
    policy = _settings(environ)["SECURE_CSP_REPORT_ONLY"]

    assert PUBLIC_BUCKET in policy["script-src"]
    assert PUBLIC_BUCKET in policy["img-src"]
    assert PRIVATE_BUCKET in policy["img-src"]
    assert PRIVATE_BUCKET not in policy["script-src"]


@pytest.mark.parametrize(
    "environ",
    [{"DEBUG": "false", "USE_S3": "false"}, {"DEBUG": "true"}],
    ids=["debug-off-without-s3", "debug-on-default"],
)
def test_policy_is_self_only_when_storage_is_local(environ):
    policy = _settings(environ)["SECURE_CSP_REPORT_ONLY"]

    assert policy["script-src"] == [CSP.SELF]
    assert policy["img-src"] == [CSP.SELF, "data:", "blob:"]


def test_policy_reports_violations_to_the_endpoint():
    policy = _settings({})["SECURE_CSP_REPORT_ONLY"]

    assert policy["report-uri"] == [reverse("csp_report")]


def test_csp_middleware_is_djangos_built_in():
    middleware = _settings({})["MIDDLEWARE"]

    assert (
        "django.middleware.csp.ContentSecurityPolicyMiddleware" in middleware
    )
    assert "csp.middleware.CSPMiddleware" not in middleware


@pytest.mark.postgres
@pytest.mark.django_db
def test_home_page_sends_the_report_only_header(client):
    response = client.get(reverse("pages:home"))

    assert "default-src 'self'" in response[CSP.HEADER_REPORT_ONLY]


REPORT = {
    "document-uri": "https://litigantportal.com/chat/?thread=abc",
    "referrer": "https://litigantportal.com/?q=eviction",
    "violated-directive": "script-src-elem",
    "effective-directive": "script-src-elem",
    "original-policy": "default-src 'self'",
    "disposition": "report",
    "blocked-uri": "https://cdn.example.com/lib.js?key=secret",
    "source-file": "https://litigantportal.com/static/js/app.js?v=1",
    "line-number": 12,
    "script-sample": "alert(document.cookie)",
    "status-code": 200,
}


@pytest.fixture
def reporter(monkeypatch):
    reporter = mock.Mock()
    monkeypatch.setattr("litigant_portal.app.views.csp.lp_logger", reporter)
    return reporter


def _report(client, body):
    return client.post(
        reverse("csp_report"), body, content_type="application/csp-report"
    )


def test_report_logs_only_the_fields_needed_to_fix_the_policy(
    client, reporter
):
    response = _report(client, json.dumps({"csp-report": REPORT}))

    assert response.status_code == 204
    reporter.assert_called_once_with(
        type=EVENTS.warning,
        msg="CSP violation",
        context={
            "directive": "script-src-elem",
            "disposition": "report",
            "blocked": "https://cdn.example.com",
            "document_path": "/chat/",
            "source_file": "https://litigantportal.com/static/js/app.js",
            "line": 12,
        },
        source="browser",
        sanitize=False,
    )


@pytest.mark.parametrize(
    ("blocked_uri", "expected"),
    [
        ("inline", "inline"),
        ("eval", "eval"),
        ("data:image/png;base64,AAAA", "data"),
        ("blob:https://litigantportal.com/1234", "blob"),
    ],
    ids=["inline", "eval", "data-url", "blob-url"],
)
def test_report_keeps_only_the_kind_of_a_non_network_blocked_uri(
    client, reporter, blocked_uri, expected
):
    report = {"effective-directive": "img-src", "blocked-uri": blocked_uri}
    _report(client, json.dumps({"csp-report": report}))

    assert reporter.call_args.kwargs["context"]["blocked"] == expected


@pytest.mark.parametrize(
    "body",
    ["not json", json.dumps([]), json.dumps({"csp-report": "x"})],
    ids=["not-json", "not-an-object", "report-not-an-object"],
)
def test_malformed_report_is_rejected_without_logging(client, reporter, body):
    assert _report(client, body).status_code == 400
    reporter.assert_not_called()


@pytest.mark.parametrize(
    "field", ["blocked-uri", "document-uri", "source-file"]
)
def test_report_with_an_unparsable_url_is_rejected_without_logging(
    client, reporter, field
):
    report = {**REPORT, field: "http://[bad"}
    response = _report(client, json.dumps({"csp-report": report}))

    assert response.status_code == 400
    reporter.assert_not_called()


def test_oversized_report_is_rejected_without_logging(client, reporter):
    report = {**REPORT, "script-sample": "x" * 20_000}
    response = _report(client, json.dumps({"csp-report": report}))

    assert response.status_code == 413
    reporter.assert_not_called()


def test_report_endpoint_rejects_get(client, reporter):
    assert client.get(reverse("csp_report")).status_code == 405
    reporter.assert_not_called()
