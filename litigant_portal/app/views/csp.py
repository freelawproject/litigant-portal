import json
import re
from urllib.parse import urlsplit

from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from litigant_portal.lp_logger import EVENTS, lp_logger

MAX_REPORT_BYTES = 16 * 1024
MAX_FIELD_LENGTH = 256
_KEYWORD = re.compile(r"[a-z-]+")


def _text(report: dict, key: str) -> str:
    value = report.get(key)
    return value[:MAX_FIELD_LENGTH] if isinstance(value, str) else ""


def _blocked(value: str) -> str:
    """Origin of a blocked URL, or the kind (inline, eval, data) otherwise."""
    parts = urlsplit(value)
    if parts.netloc:
        return f"{parts.scheme}://{parts.netloc}"
    kind = value.split(":", 1)[0]
    return kind if _KEYWORD.fullmatch(kind) else ""


def _without_query(value: str) -> str:
    parts = urlsplit(value)
    return (
        f"{parts.scheme}://{parts.netloc}{parts.path}" if parts.netloc else ""
    )


@csrf_exempt
@require_POST
@ratelimit(key="ip", rate="20/m", method="POST", block=True)
def csp_report(request: HttpRequest) -> HttpResponse:
    """Log a browser's CSP violation report, without query strings or code
    samples."""
    body = request.read(MAX_REPORT_BYTES + 1)
    if len(body) > MAX_REPORT_BYTES:
        return HttpResponse(status=413)
    try:
        report = json.loads(body)["csp-report"]
    except (KeyError, TypeError, ValueError, RecursionError):
        return HttpResponse(status=400)
    if not isinstance(report, dict):
        return HttpResponse(status=400)

    line = report.get("line-number")
    try:
        context = {
            "directive": _text(report, "effective-directive")
            or _text(report, "violated-directive"),
            "disposition": _text(report, "disposition"),
            "blocked": _blocked(_text(report, "blocked-uri")),
            "document_path": urlsplit(_text(report, "document-uri")).path,
            "source_file": _without_query(_text(report, "source-file")),
            "line": line if isinstance(line, int) else None,
        }
    except ValueError:
        return HttpResponse(status=400)
    lp_logger(
        type=EVENTS.warning,
        msg="CSP violation",
        context={key: value for key, value in context.items() if value},
        source="browser",
        sanitize=False,
    )
    return HttpResponse(status=204)
