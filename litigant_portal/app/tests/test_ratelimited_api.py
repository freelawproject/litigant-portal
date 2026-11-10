"""Tests for the JSON answer to a tripped @ratelimit on the API views,
and for the address the limit counts by.

DB-free: a POST with no file is refused before the view touches identity
or the database. The test client sends every request from one
REMOTE_ADDR, as the proxy does in production.
"""

from django.urls import reverse

VIEWER_A = {"CloudFront-Viewer-Address": "203.0.113.10:5000"}
VIEWER_B = {"CloudFront-Viewer-Address": "203.0.113.20:5000"}


def test_upload_limit_answers_json_429_not_html_403(ratelimited, client):
    url = reverse("assistant:upload_create")
    for _ in range(20):
        assert client.post(url).status_code == 400

    response = client.post(url)

    assert response.status_code == 429
    assert response["Content-Type"] == "application/json"
    assert response.json() == {
        "error": "Too many requests. Wait a minute and try again."
    }


def test_upload_limit_counts_each_viewer_address_apart(
    ratelimited, behind_cloudfront, client
):
    url = reverse("assistant:upload_create")
    for _ in range(20):
        client.post(url, headers=VIEWER_A)

    assert client.post(url, headers=VIEWER_A).status_code == 429
    assert client.post(url, headers=VIEWER_B).status_code == 400


def test_upload_limit_ignores_x_forwarded_for(
    ratelimited, behind_cloudfront, client
):
    url = reverse("assistant:upload_create")
    for _ in range(20):
        client.post(url, headers=VIEWER_A)

    for forwarded_for in ("198.51.100.7", "198.51.100.8"):
        response = client.post(
            url, headers={**VIEWER_A, "X-Forwarded-For": forwarded_for}
        )
        assert response.status_code == 429


def test_upload_limit_counts_a_malformed_viewer_address_as_remote_addr(
    ratelimited, behind_cloudfront, client
):
    url = reverse("assistant:upload_create")
    malformed = {"CloudFront-Viewer-Address": "not-an-ip:1234"}
    for _ in range(20):
        assert client.post(url, headers=malformed).status_code == 400

    assert client.post(url, headers=malformed).status_code == 429
    assert client.post(url).status_code == 429


def test_upload_limit_counts_an_untrusted_viewer_address_as_remote_addr(
    ratelimited, client
):
    url = reverse("assistant:upload_create")
    for _ in range(20):
        client.post(url, headers=VIEWER_A)

    assert client.post(url, headers=VIEWER_B).status_code == 429
