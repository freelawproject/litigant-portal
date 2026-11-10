"""DB-free tests: the visitor address rate limits count by.

With TRUST_CLOUDFRONT_VIEWER_ADDRESS on, CloudFront's
``CloudFront-Viewer-Address`` (``IP:port``) is the address. Anything
else falls back to ``REMOTE_ADDR``.
"""

import logging

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import RequestFactory

from litigant_portal.app.client_ip import get_client_ip

REMOTE_ADDR = "10.0.0.5"


def _request(viewer_address=None, remote_addr=REMOTE_ADDR, **headers):
    if viewer_address is not None:
        headers["CloudFront-Viewer-Address"] = viewer_address
    return RequestFactory(REMOTE_ADDR=remote_addr).get("/", headers=headers)


@pytest.mark.parametrize(
    ("viewer_address", "expected"),
    [
        ("96.23.39.106:51396", "96.23.39.106"),
        ("2600:1f18::1234:51396", "2600:1f18::1234"),
        ("[2600:1f18::1234]:51396", "2600:1f18::1234"),
        ("::ffff:96.23.39.106:51396", "96.23.39.106"),
    ],
    ids=[
        "ipv4",
        "ipv6-unbracketed",
        "ipv6-bracketed",
        "ipv4-mapped-ipv6",
    ],
)
def test_viewer_address_gives_the_address_without_the_port(
    behind_cloudfront, viewer_address, expected
):
    assert get_client_ip(_request(viewer_address)) == expected


def test_viewer_address_is_ignored_when_not_trusted(caplog):
    with caplog.at_level(logging.WARNING):
        ip = get_client_ip(_request("96.23.39.106:51396"))

    assert ip == REMOTE_ADDR
    assert caplog.records == []


def test_no_header_gives_remote_addr(behind_cloudfront):
    assert get_client_ip(_request()) == REMOTE_ADDR


@pytest.mark.parametrize(
    "viewer_address",
    ["not-an-ip:1234", "", "96.23.39.106", "96.23.39.106, 1.2.3.4:80"],
    ids=["not-an-address", "empty", "no-port", "two-addresses"],
)
def test_malformed_header_gives_remote_addr(behind_cloudfront, viewer_address):
    assert get_client_ip(_request(viewer_address)) == REMOTE_ADDR


@pytest.mark.parametrize(
    "viewer_address", [None, "not-an-ip:1234"], ids=["missing", "malformed"]
)
def test_trusted_header_that_gives_no_address_logs_a_warning(
    behind_cloudfront, caplog, viewer_address
):
    with caplog.at_level(logging.WARNING):
        get_client_ip(_request(viewer_address))

    assert [record.levelname for record in caplog.records] == ["WARNING"]
    assert "CloudFront-Viewer-Address" in caplog.text


def test_empty_remote_addr_raises():
    with pytest.raises(ImproperlyConfigured):
        get_client_ip(_request(remote_addr=""))


def test_x_forwarded_for_is_ignored_without_the_header(behind_cloudfront):
    request = _request(**{"X-Forwarded-For": "198.51.100.7"})

    assert get_client_ip(request) == REMOTE_ADDR


def test_x_forwarded_for_is_ignored_with_the_header(behind_cloudfront):
    request = _request(
        "96.23.39.106:51396", **{"X-Forwarded-For": "198.51.100.7"}
    )

    assert get_client_ip(request) == "96.23.39.106"
