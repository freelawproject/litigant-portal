# Application logging with lp_logger

`litigant_portal.lp_logger` wraps Django's configured Python logger with sanitization, automatic metadata, and target routing.

```python
from litigant_portal.lp_logger import EVENTS, TARGETS, lp_logger

lp_logger(
    type=EVENTS.warning,
    msg="Assistant is temporarily unavailable",
    context={"status_code": 503},
)

# An existing exception supplies its type, severity, and code locations.
lp_logger(type=error, msg="Assistant model discovery failed")
```

`EVENTS` exposes Python's debug, info, warning, error, and critical levels. An exception instance maps to error, or warning for a `Warning` instance. The event type is the severity name or the qualified exception class. No event registration is required.

`msg` is optional. Python call sites must use a literal string. The wrapper never substitutes placeholders. Put dynamic data in `context`. The pre-commit source check rejects interpolation, variable messages, and unpacked logger arguments, including when sanitization is disabled. Import `lp_logger` directly (optionally using an import alias) or call it through its module. Absolute and package-relative imports are supported; relative imports that cannot be resolved are rejected. Do not rebind it or invoke it indirectly. The HTTP adapter is excluded from this source check because it forwards validated runtime arguments. Source checks cannot establish whether browser-supplied text was originally a literal.

Sanitization runs before a log record is created. Context allows only an integer `status_code` from 100 through 599. Unknown fields and unsupported values are dropped. Default exception output contains code filenames, functions, and line numbers. It excludes exception messages, arguments, source lines, local values, and raw exception objects. Private facts, chat, prompts, uploads, secrets, URLs, and user/session identifiers have no allowed context fields.

Trusted Python callers may explicitly pass `sanitize=False` to include raw context and standard exception tracebacks, including exception text and chained exceptions. This works in production too. Messages must still be literals. Context must remain JSON serializable. There is no automatic detection of arbitrary PII in free text.

Timestamps and caller information come from Python's log records. Environment and release use `DEPLOYMENT_ENV` and `GIT_SHA`. Python's `source` defaults to `server`; `source="worker"`, `"command"`, or `"browser"` can override it.

Every enabled log call writes structured JSON to stdout, including calls with an empty target list. Targets select additional handlers. The default is `TARGETS.observe`; pass `target=[TARGETS.observe, TARGETS.analytics]` to select both. Target lists are deduplicated.

Django's `LOGGING` settings run `lp_stdout` first, followed by the `lp_observe` and `lp_analytics` handlers. Each target handler uses `TargetFilter` and a separate instance of `ExampleTargetHandler`. Both instances are no-ops and make no external requests. They receive the same formatted JSON event as stdout, with the caller's sanitization policy already applied.

To connect a service, subclass `ExampleTargetHandler`, implement `send(message)`, and set the corresponding handler's `class` in `LOGGING`. `send()` is the service boundary for an observability or analytics client. Its failures are contained within that handler so other selected targets still run and the server log remains available.

The named logger does not propagate to parent handlers. Calls are best effort and return no delivery acknowledgement. A failing stdout handler can drop that log attempt; it cannot raise into the application's flow or recursively call the logger. The stdout handler avoids Python's default error diagnostic, which can expose the active exception chain. Distinct occurrences are logged separately.

The assistant model-unavailable handler uses `lp_logger`. Other application components use Python module loggers and browser console output. Stored chat transcripts and user-facing Django messages have separate responsibilities.

## Browser calls

```javascript
window.lpLogger({
  type: 'warning',
  msg: 'Request failed',
  context: { status_code: 503 },
})
```

`lpLogger` starts a POST to `/api/logs/` and immediately calls native `console.log(options)` with the original options, without waiting for the request. Native `Error` instances become severity `error` for transport and remain intact in the console. Serialization or request failures do not prevent console output.

The endpoint validates argument shapes, rejects messages longer than 1,024 characters with HTTP 400 before logging, converts severity and target names, and forwards the options to Python's `lp_logger` with `source="browser"` and sanitization enabled. Python owns metadata, routing, and context filtering. Accepted messages pass through unchanged; neither runtime detects arbitrary PII in message text, and local console output is unfiltered. Requests include Django's CSRF token and omit the page referrer. The endpoint applies the existing 20-per-minute IP rate-limit pattern and returns 202 for best-effort logging.
