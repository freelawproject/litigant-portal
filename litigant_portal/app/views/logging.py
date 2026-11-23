import json

from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from litigant_portal.lp_logger import EVENTS, TARGETS, lp_logger

MAX_MESSAGE_LENGTH = 1024


@require_POST
@ratelimit(key="ip", rate="20/m", method="POST", block=True)
def browser_log(request: HttpRequest) -> HttpResponse:
    try:
        options = json.loads(request.POST["options"])
        if not isinstance(options, dict) or set(options) - {
            "type",
            "msg",
            "target",
            "context",
        }:
            return HttpResponse(status=400)
        for name, kind in (("msg", str), ("context", dict), ("target", list)):
            if options.get(name) is not None and not isinstance(
                options[name], kind
            ):
                return HttpResponse(status=400)
        message = options.get("msg")
        if message is not None and len(message) > MAX_MESSAGE_LENGTH:
            return HttpResponse(status=400)
        event_type = options["type"]
        options["type"] = (
            EVENTS.__members__[event_type.lower()]
            if isinstance(event_type, str)
            else EVENTS(event_type)
        )
        if "target" in options:
            options["target"] = [TARGETS(value) for value in options["target"]]
        lp_logger(**options, source="browser", sanitize=True)
    except (KeyError, TypeError, ValueError):
        return HttpResponse(status=400)
    return HttpResponse(status=202)
