"""
Docassemble prefill mapping and session handoff.

Three calls, in order: create a session, set its variables, mint a one-time
resume URL for the litigant's browser. Answers travel in a POST body, never
in a URL, and the API key travels in a header.

The target interview must set ``multi_user = True`` from an ``initial`` code
block, or its session is encrypted per-browser and the resume URL cannot
decrypt it.

The separate request_interview lifecycle entrypoint remains a no-op.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import urlencode, urlparse, urlunparse

import requests
from django.conf import settings

from litigant_portal.state.types import StateType

if TYPE_CHECKING:
    from litigant_portal.state.models import TopicFlow

logger = logging.getLogger(__name__)

_TIMEOUT = 10
# Short enough that a leaked link in shared-terminal history is dead, long
# enough for a slow redirect.
_RESUME_EXPIRY_SECONDS = 600


class DocassembleError(Exception):
    """
    A session could not be created.

    Callers fall back to the plain interview link: unprefilled beats a dead
    button.
    """


def docassemble_configured() -> bool:
    """
    Whether this environment has a docassemble to hand off to.

    The single rule behind the launch link and the deploy-time check: either
    base is enough for the plain link, so the button renders.
    """
    return bool(
        settings.DOCASSEMBLE_PUBLIC_URL or settings.DOCASSEMBLE_BASE_URL
    )


def interview_launch_url(interview: str) -> str | None:
    """
    The litigant-facing launch link for an interview reference.

    Built from configuration, never from content: the public base when LP
    reaches docassemble at an address litigants cannot, else the API base.
    ``None`` means no Docassemble is configured; callers hide the handoff.
    """
    if not docassemble_configured():
        return None
    base = settings.DOCASSEMBLE_PUBLIC_URL or settings.DOCASSEMBLE_BASE_URL
    return f"{base.rstrip('/')}/interview?{urlencode({'i': interview})}"


def docassemble_session_create(*, interview: str, variables: dict) -> str:
    """
    Return a one-time URL onto a new session prefilled with ``variables``.

    ``interview`` is the reference from the corpus packet section (the ``?i=``
    value); where it is sent comes from settings alone. Keys in ``variables``
    are interview-side names, which docassemble executes as assignment
    statements, so they may only come from author-controlled YAML.
    """
    api_root = settings.DOCASSEMBLE_BASE_URL
    if not api_root:
        raise DocassembleError("DOCASSEMBLE_BASE_URL is unset")
    api_root = api_root.rstrip("/")
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
    """
    Swap in the litigant-facing base, keeping docassemble's path and query.

    docassemble builds the launch URL from the host we called it on, which on
    a deployment is an internal address no browser can reach. The public URL's
    origin replaces it, and its path prefix (docassemble served under a
    subpath) is prepended unless docassemble's own url root already put it
    there. Unset means the URL comes back as docassemble built it.
    """
    public = settings.DOCASSEMBLE_PUBLIC_URL
    if not public:
        return resume_url
    target = urlparse(public)
    resume = urlparse(resume_url)
    prefix = target.path.rstrip("/")
    path = resume.path
    # startswith wants the trailing slash: a path merely *equal* to the
    # prefix is docassemble's /interview endpoint colliding with an
    # /interview prefix, and still needs the prefix in front.
    if prefix and not path.startswith(prefix + "/"):
        path = prefix + path
    return urlunparse(
        resume._replace(scheme=target.scheme, netloc=target.netloc, path=path)
    )


def _call(
    *, method: str, api_root: str, path: str, api_key: str, **kwargs
) -> requests.Response:
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


def flow_interview_target(
    flow: TopicFlow,
) -> tuple[str, dict[str, str]] | None:
    """
    Return the interview reference and mapping, or None without a reference.
    """
    if not flow.interview_reference:
        return None
    return flow.interview_reference, dict(flow.interview_prefill)


def prefill_variables(*, mapping: dict[str, str], answers: dict) -> dict:
    """
    Rename the caller's confirmed, applicable answers for the interview.

    An unanswered question is absent rather than blank, so the interview asks
    it. Values pass through untouched: a stored date is already the ISO string
    docassemble parses back into a date object.
    """
    return {
        variable: answers[question_id]
        for question_id, variable in mapping.items()
        if question_id in answers
    }


def request_interview(state: StateType, interview_reference: str) -> None:
    """
    Reserve the lifecycle handoff boundary without executing an operation.

    Phase 1 deliberately produces no session, result, or completion state.
    User-initiated launches use docassemble_session_create separately.
    """
