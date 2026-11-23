"""Tests for the Content Security Policy header.

The settings tests load settings.py under a controlled environment and are
DB-free; the home page header test is postgres-marked.
"""

import os
import runpy
from unittest import mock

import pytest
from django.urls import reverse
from django.utils.csp import CSP

import litigant_portal.settings

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


def test_policy_allows_the_s3_origins_when_debug_is_off():
    policy = _settings({"DEBUG": "false"})["SECURE_CSP_REPORT_ONLY"]

    assert PUBLIC_BUCKET in policy["script-src"]
    assert PUBLIC_BUCKET in policy["img-src"]
    assert PRIVATE_BUCKET in policy["img-src"]
    assert PRIVATE_BUCKET not in policy["script-src"]


def test_policy_is_self_only_when_debug_is_on():
    policy = _settings({"DEBUG": "true"})["SECURE_CSP_REPORT_ONLY"]

    assert policy["script-src"] == [CSP.SELF]
    assert policy["img-src"] == [CSP.SELF, "data:", "blob:"]


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
