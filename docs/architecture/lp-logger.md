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

`msg` is optional and must be a literal string. The wrapper never substitutes placeholders. Put dynamic data in `context`. The pre-commit source check rejects interpolation, variable messages, and unpacked logger arguments, including when sanitization is disabled. Import `lp_logger` directly (optionally using an import alias) or call it through its module. Do not rebind it or invoke it indirectly. This source check is a development guard, not validation for untrusted callers.

Sanitization runs before a log record is created. Context allows only an integer `status_code` from 100 through 599. Unknown fields and unsupported values are dropped. Default exception output contains code filenames, functions, and line numbers. It excludes exception messages, arguments, source lines, local values, and raw exception objects. Private facts, chat, prompts, uploads, secrets, URLs, and user/session identifiers have no allowed context fields.

Trusted Python callers may explicitly pass `sanitize=False` to include raw context and standard exception tracebacks, including exception text and chained exceptions. This works in production too. Messages must still be literals. Context must remain JSON serializable. There is no automatic detection of arbitrary PII in free text.

Timestamps and caller information come from Python's log records. Environment and release use `DEPLOYMENT_ENV` and `GIT_SHA`. Python's `source` defaults to `server`; `source="worker"`, `"command"`, or `"browser"` can override it.

The default target is `TARGETS.observe`, which writes structured logs to stdout. Target lists are deduplicated. `TARGETS.analytics` has no configured handler and produces no output. Handlers are configured through Django's `LOGGING` settings and use `TargetFilter` to select records by target.

The named logger does not propagate to parent handlers. Calls are best effort and return no delivery acknowledgement. A failing handler can drop that log attempt; it cannot raise into the application's flow or recursively call the logger. The stdout handler avoids Python's default error diagnostic, which can expose the active exception chain. Distinct occurrences are logged separately.

The assistant model-unavailable handler uses `lp_logger`. Other application components use Python module loggers and browser console output. Stored chat transcripts and user-facing Django messages have separate responsibilities.
