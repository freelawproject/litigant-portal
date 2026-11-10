"""DB-free tests: the address allauth's rate limits count by."""

from allauth.account.adapter import get_adapter
from django.test import RequestFactory


def test_client_ip_is_the_cloudfront_viewer_address(behind_cloudfront):
    request = RequestFactory(REMOTE_ADDR="10.0.0.5").get(
        "/", headers={"CloudFront-Viewer-Address": "203.0.113.10:5000"}
    )

    assert get_adapter().get_client_ip(request) == "203.0.113.10"
