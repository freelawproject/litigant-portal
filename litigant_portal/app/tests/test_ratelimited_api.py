"""Tests for the JSON answer to a tripped @ratelimit on the API views.

DB-free: a POST with no file is refused before the view touches identity
or the database.
"""

from django.urls import reverse


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
