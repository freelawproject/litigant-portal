import json
import logging
import traceback
from collections.abc import Mapping, Sequence
from contextvars import ContextVar
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from pathlib import Path
from typing import Literal, LiteralString

from django.conf import settings


class EventType(IntEnum):
    debug = logging.DEBUG
    info = logging.INFO
    warning = logging.WARNING
    error = logging.ERROR
    critical = logging.CRITICAL


class TargetType(StrEnum):
    observe = "observe"
    analytics = "analytics"


EVENTS = EventType
TARGETS = TargetType
_logger = logging.getLogger(__name__)
_reporting = ContextVar("lp_logger_reporting", default=False)


def _sanitize_context(context: Mapping[str, object]) -> dict[str, object]:
    status = context.get("status_code")
    if (
        isinstance(status, int)
        and not isinstance(status, bool)
        and 100 <= status <= 599
    ):
        return {"status_code": status}
    return {}


def lp_logger(
    *,
    type: EventType | Exception,
    msg: LiteralString | None = None,
    target: Sequence[TargetType] = (TARGETS.observe,),
    context: Mapping[str, object] | None = None,
    source: Literal["server", "browser", "worker", "command"] = "server",
    sanitize: bool = True,
) -> None:
    """
    Report through Django logging with privacy applied before any handler.

    Messages must be source literals. Dynamic values belong in context.
    Disabling sanitization explicitly allows raw context and exception details.
    Delivery is best effort, and reporting failures never propagate to callers.
    """
    if _reporting.get():
        return
    token = _reporting.set(True)
    try:
        if source not in ("server", "browser", "worker", "command"):
            return
        if isinstance(type, Exception):
            exception = type
            level = (
                EVENTS.warning
                if isinstance(exception, Warning)
                else EVENTS.error
            )
            event_type = f"{exception.__class__.__module__}.{exception.__class__.__qualname__}"
        else:
            exception = None
            level = EventType(type)
            event_type = level.name
        if not _logger.isEnabledFor(level):
            return

        error = None
        if exception is not None:
            # Walk code locations only; never extract source lines or locals.
            error = {
                "stack": [
                    {
                        "file": Path(frame.f_code.co_filename).name,
                        "function": frame.f_code.co_name,
                        "line": line,
                    }
                    for frame, line in traceback.walk_tb(
                        exception.__traceback__
                    )
                ]
            }
        details = context if context is not None else {}
        _logger.log(
            level,
            msg if msg is not None else event_type,
            extra={
                "event_type": event_type,
                "targets": tuple(
                    dict.fromkeys(TargetType(value) for value in target)
                ),
                "source": source,
                "environment": settings.DEPLOYMENT_ENV,
                "release": settings.GIT_SHA,
                "context": _sanitize_context(details)
                if sanitize
                else dict(details),
                "error": error,
            },
            exc_info=exception if not sanitize else None,
            stacklevel=2,
        )
    except Exception:
        # Reporting must not replace an application failure or recurse.
        return
    finally:
        _reporting.reset(token)


class TargetFilter(logging.Filter):
    def __init__(self, target: str) -> None:
        super().__init__()
        self.target = TargetType(target)

    def filter(self, record: logging.LogRecord) -> bool:
        return self.target in record.__dict__.get("targets", ())


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        fields = vars(record)
        event = {
            "timestamp": datetime.fromtimestamp(
                record.created, UTC
            ).isoformat(),
            "type": fields["event_type"],
            "level": record.levelname,
            "component": record.module,
            "function": record.funcName,
            "source": fields["source"],
            "environment": fields["environment"],
            "release": fields["release"],
            "message": record.getMessage(),
            "context": fields["context"],
        }
        if fields["error"] is not None:
            event["error"] = fields["error"]
        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event)


class SafeStreamHandler(logging.StreamHandler):
    def handleError(self, record: logging.LogRecord) -> None:
        # The default handler can print the active exception and its context.
        # Let lp_logger contain the failure without exposing that traceback.
        raise
