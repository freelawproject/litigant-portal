import json
import logging
from datetime import datetime
from io import StringIO
from unittest.mock import Mock

import pytest

from litigant_portal.lp_logger import EVENTS, TARGETS, lp_logger


@pytest.fixture
def output(monkeypatch):
    handler = logging.getHandlerByName("lp_stdout")
    stream = StringIO()
    monkeypatch.setattr(handler, "stream", stream)
    records = []
    handler.addFilter(lambda record: records.append(record) or True)
    yield stream, records
    handler.filters.pop()


def test_private_data_never_reaches_handler(output, settings):
    settings.DEPLOYMENT_ENV = "qa"
    settings.GIT_SHA = "test-release"
    stream, records = output
    try:
        raise ValueError("private exception text")
    except ValueError as error:
        lp_logger(
            type=error,
            msg="Request failed",
            context={"status_code": 503, "chat": "private chat text"},
        )
    event = json.loads(stream.getvalue())
    assert event["type"] == "builtins.ValueError"
    assert event["level"] == "ERROR"
    assert event["context"] == {"status_code": 503}
    assert event["environment"] == "qa"
    assert event["release"] == "test-release"
    assert event["source"] == "server"
    assert event["component"] == "test_lp_logger"
    assert event["function"] == "test_private_data_never_reaches_handler"
    assert (
        datetime.fromisoformat(event["timestamp"]).utcoffset().total_seconds()
        == 0
    )
    assert event["error"]["stack"][-1]["file"] == "test_lp_logger.py"
    assert len(records) == 1
    assert records[0].exc_info is None
    assert records[0].exc_text is None
    assert "private exception text" not in repr(vars(records[0]))
    assert "private chat text" not in repr(vars(records[0]))


def test_routing_and_explicit_unsanitized_exception(output):
    stream, records = output
    lp_logger(type=EVENTS.info, target=[TARGETS.analytics])
    assert records == []
    try:
        raise UserWarning("debug detail")
    except UserWarning as error:
        lp_logger(
            type=error,
            msg="Warning at {time_variable}",
            target=[TARGETS.observe, TARGETS.observe],
            source="worker",
            context={"debug_detail": "explicitly included"},
            sanitize=False,
        )
    event = json.loads(stream.getvalue())
    assert len(records) == 1
    assert event["level"] == "WARNING"
    assert event["source"] == "worker"
    assert event["message"] == "Warning at {time_variable}"
    assert event["context"] == {"debug_detail": "explicitly included"}
    assert "UserWarning: debug detail" in event["exception"]


@pytest.mark.parametrize(
    "status", [True, "503", 99, 600, {"private": "value"}]
)
def test_context_rejects_invalid_status_codes(output, status):
    stream, _ = output
    lp_logger(type=EVENTS.warning, context={"status_code": status})
    assert json.loads(stream.getvalue())["context"] == {}


def test_failing_reentrant_sink_does_not_print_tracebacks(
    output, monkeypatch, capsys
):
    def fail_write(message):
        lp_logger(type=EVENTS.error, msg="Recursive report")
        raise OSError("private sink failure")

    stream, _ = output
    write = Mock(side_effect=fail_write)
    monkeypatch.setattr(stream, "write", write)
    try:
        raise ValueError("private original error")
    except ValueError as error:
        lp_logger(type=error)
    write.assert_called_once()
    assert capsys.readouterr().err == ""
