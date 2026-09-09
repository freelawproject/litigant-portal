"""docassemble API client: start a prefilled interview session.

Three calls, in order: create a session, set its variables, mint a one-time
resume URL for the litigant's browser. Answers travel in a POST body, never
in a URL, and the API key travels in a header.

The target interview must set ``multi_user = True`` from an ``initial`` code
block, or its session is encrypted per-browser and the resume URL cannot
decrypt it.
"""

import logging
from urllib.parse import parse_qs, urlparse, urlunparse

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 10
# Short enough that a leaked link in shared-terminal history is dead, long
# enough for a slow redirect.
_RESUME_EXPIRY_SECONDS = 600


class DocassembleError(Exception):
    """A session could not be created.

    Callers fall back to the plain interview link: unprefilled beats a dead
    button.
    """


def docassemble_session_create(*, interview_url: str, variables: dict) -> str:
    """Return a one-time URL onto a new session prefilled with ``variables``.

    ``interview_url`` is the plain launch link from the corpus packet section,
    carrying the interview reference in its ``?i=`` parameter. Keys in
    ``variables`` are interview-side names, which docassemble executes as
    assignment statements, so they may only come from author-controlled YAML.
    """
    api_root, interview = _target(interview_url)
    api_key = settings.DOCASSEMBLE_API_KEY
    if not api_key:
        raise DocassembleError("DOCASSEMBLE_API_KEY is unset")

    session = _session_new(api_root, api_key, interview)
    try:
        _variables_set(api_root, api_key, interview, session, variables)
        return _public(_resume_url(api_root, api_key, interview, session))
    except DocassembleError:
        # The session may already hold the litigant's answers, and nothing
        # will ever resume it (#805 covers only downloaded packets), so
        # delete it rather than leave the data orphaned. Best effort: the
        # caller acts on the original error either way.
        _session_delete(api_root, api_key, interview, session)
        raise


def _session_delete(
    api_root: str, api_key: str, interview: str, session: str
) -> None:
    try:
        _call(
            method="DELETE",
            api_root=api_root,
            path="session",
            api_key=api_key,
            params={"i": interview, "session": session},
        )
    except DocassembleError:
        logger.warning(
            "orphaned docassemble session could not be deleted", exc_info=True
        )


def _public(resume_url: str) -> str:
    """Swap in the litigant-facing origin, keeping the path and query.

    docassemble builds the launch URL from the host we called it on, which on
    a deployment is an internal address no browser can reach. Unset means the
    URL comes back as docassemble built it.
    """
    public = settings.DOCASSEMBLE_PUBLIC_URL
    if not public:
        return resume_url
    origin = urlparse(public)
    return urlunparse(
        urlparse(resume_url)._replace(
            scheme=origin.scheme, netloc=origin.netloc
        )
    )


def _target(interview_url: str) -> tuple[str, str]:
    """``(api root, interview reference)`` for a launch link."""
    parts = urlparse(interview_url)
    references = parse_qs(parts.query).get("i", [])
    if not references:
        raise DocassembleError(f"No ?i= interview in {interview_url!r}")
    # The API sits beside the launch route, so drop that last segment: QA's
    # /interview/interview leaves the /interview/ path prefix in place.
    root = settings.DOCASSEMBLE_BASE_URL or (
        f"{parts.scheme}://{parts.netloc}{parts.path.rsplit('/', 1)[0]}"
    )
    return root.rstrip("/"), references[0]


def _call(*, method: str, api_root: str, path: str, api_key: str, **kwargs):
    url = f"{api_root}/api/{path}"
    try:
        response = requests.request(
            method,
            url,
            headers={"X-API-Key": api_key},
            timeout=_TIMEOUT,
            **kwargs,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        # No variables in the message: it reaches logs and error reporting.
        raise DocassembleError(f"docassemble {path} failed: {exc}") from exc
    return response


def _session_new(api_root: str, api_key: str, interview: str) -> str:
    response = _call(
        method="GET",
        api_root=api_root,
        path="session/new",
        api_key=api_key,
        params={"i": interview},
    )
    try:
        return response.json()["session"]
    except (ValueError, KeyError, TypeError) as exc:
        raise DocassembleError("No session in session/new response") from exc


def _variables_set(
    api_root: str,
    api_key: str,
    interview: str,
    session: str,
    variables: dict,
) -> None:
    # question=0 skips interview evaluation, so nothing assembles on our
    # request and a 204 comes back.
    _call(
        method="POST",
        api_root=api_root,
        path="session",
        api_key=api_key,
        json={
            "i": interview,
            "session": session,
            "variables": variables,
            "question": 0,
        },
    )


def _resume_url(
    api_root: str, api_key: str, interview: str, session: str
) -> str:
    response = _call(
        method="POST",
        api_root=api_root,
        path="resume_url",
        api_key=api_key,
        json={
            "i": interview,
            "session": session,
            "one_time": 1,
            "expire": _RESUME_EXPIRY_SECONDS,
        },
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise DocassembleError("Unreadable resume_url response") from exc
    url = payload.get("url") if isinstance(payload, dict) else payload
    if not isinstance(url, str) or not url:
        raise DocassembleError("No URL in resume_url response")
    return url
