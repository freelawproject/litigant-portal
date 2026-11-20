import json
from unittest.mock import Mock
from urllib.parse import urlencode

import pytest
from django.test import Client
from django.urls import reverse


def post(client, options):
    return client.post(
        reverse("browser_log"),
        urlencode({"options": json.dumps(options)}),
        content_type="application/x-www-form-urlencoded",
    )


def test_browser_log_forwards_options(client, monkeypatch):
    reporter = Mock()
    monkeypatch.setattr(
        "litigant_portal.app.views.logging.lp_logger", reporter
    )
    assert (
        post(
            client,
            {
                "type": "warning",
                "msg": "Request failed",
                "context": {"status_code": 503},
            },
        ).status_code
        == 202
    )
    from litigant_portal.lp_logger import EVENTS

    reporter.assert_called_once_with(
        type=EVENTS.warning,
        msg="Request failed",
        context={"status_code": 503},
        source="browser",
        sanitize=True,
    )


@pytest.mark.parametrize(
    "message, status",
    [(None, 202), ("", 202), ("x" * 1024, 202), ("x" * 1025, 400)],
)
def test_browser_log_message_length(client, monkeypatch, message, status):
    reporter = Mock()
    monkeypatch.setattr(
        "litigant_portal.app.views.logging.lp_logger", reporter
    )
    assert post(client, {"type": "info", "msg": message}).status_code == status
    if status == 202:
        reporter.assert_called_once()
        assert reporter.call_args.kwargs["msg"] == message
    else:
        reporter.assert_not_called()


@pytest.mark.parametrize(
    "options",
    [
        [],
        {"type": "unknown"},
        {"type": "info", "msg": []},
        {"type": "info", "context": []},
        {"type": "info", "target": "observe"},
        {"type": "info", "sanitize": False},
        {"type": "info", "source": "server"},
    ],
)
def test_browser_log_rejects_invalid_options(client, options):
    assert post(client, options).status_code == 400


def test_browser_log_requires_csrf():
    assert (
        post(Client(enforce_csrf_checks=True), {"type": "info"}).status_code
        == 403
    )
