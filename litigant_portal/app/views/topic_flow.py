import json
import logging

from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import Resolver404, resolve
from django.utils.translation import gettext as _
from django.views.csrf import csrf_failure as _django_csrf_failure
from django.views.decorators.http import require_POST

from litigant_portal.app.services.docassemble import (
    DocassembleError,
    docassemble_session_create,
    interview_launch_url,
)
from litigant_portal.app.services.topic_flow import variable_answer_confirm
from litigant_portal.app.topic_flow.downloads import (
    build_download,
    find_downloadable,
)
from litigant_portal.app.topic_flow.prefill import (
    interview_target,
    prefill_variables,
)
from litigant_portal.app.topic_flow.registry import registry
from litigant_portal.app.views.utils import (
    _has_identity,
    topic_flow_answers,
    topic_flow_reviewed_answers,
)

logger = logging.getLogger(__name__)


def topic_flow_download(request, court, topic, role, output_id):
    """Download a Topic Flow output section as a file (e.g. an ``.ics``).

    The endpoint counterpart to the ``pages.topic_flow`` render: resolve the
    corpus and the downloadable output section (404 on either miss — an
    unknown id or a non-downloadable section), then dispatch on
    ``output_type`` to assemble the file from the visitor's stored answers.
    The view stays thin — file bytes come from the download handlers in
    downloads.py, computed from the same stored answers the page renders, so
    the download matches what's on screen.
    """
    corpus = registry.get(court, topic, role)
    if corpus is None:
        raise Http404(f"No Topic Flow for {court}/{topic}/{role}")

    section = find_downloadable(corpus, output_id)
    if section is None:
        raise Http404(f"No downloadable output {output_id!r}")

    artifact = build_download(
        section, corpus, topic_flow_answers(request, corpus)
    )
    response = HttpResponse(artifact.body, content_type=artifact.content_type)
    response["Content-Disposition"] = (
        f'attachment; filename="{artifact.filename}"'
    )
    return response


@require_POST
def topic_flow_interview(request, court, topic, role):
    """Start a prefilled docassemble session and send the litigant to it.

    POST because creating the session is a side effect. Only reviewed answers
    are sent: a prefilled variable skips its interview question, so docassemble
    never asks the litigant to confirm it.

    Any failure redirects to the plain interview link instead. Unprefilled is a
    worse handoff than prefilled, but a dead button is worse than both.
    """
    corpus = registry.get(court, topic, role)
    if corpus is None:
        raise Http404(f"No Topic Flow for {court}/{topic}/{role}")

    target = interview_target(corpus)
    if target is None:
        raise Http404(f"No interview handoff for {court}/{topic}/{role}")
    interview, mapping = target
    launch_url = interview_launch_url(interview)
    if launch_url is None:
        # No docassemble configured in this environment; the packet section
        # hides the button, so only a stale or hand-built POST lands here.
        raise Http404(f"No docassemble configured for {court}/{topic}/{role}")

    variables = prefill_variables(
        mapping=mapping,
        answers=topic_flow_reviewed_answers(request, list(mapping)),
    )
    if not variables:
        # Nothing to prefill: a session would cost three API calls and an
        # unencrypted multi_user session holding nothing, for the same
        # experience the plain link gives.
        return redirect(launch_url)
    try:
        resume_url = docassemble_session_create(
            interview=interview, variables=variables
        )
    except DocassembleError:
        logger.warning(
            "docassemble prefill unavailable for %s/%s/%s; "
            "falling back to the plain interview link",
            court,
            topic,
            role,
            exc_info=True,
        )
        return redirect(launch_url)
    return redirect(resume_url)


@require_POST
def topic_flow_confirm(request):
    """Mark the visitor's stored answers as reviewed by the visitor.

    Deliberately NOT an agent tool and not under the ``/api/agents/``
    namespace: only a human action may set ``reviewed=True``, because
    reviewed answers prefill the docassemble interview and skip their
    questions there. This stays a session-authenticated, CSRF-protected
    page endpoint the model cannot reach.

    Accepts a JSON body ``{"names": [...]}`` or a form-encoded ``names``
    list; responds ``{"confirmed": n}``.
    """
    if not _has_identity(request):
        return JsonResponse({"error": _("Forbidden")}, status=403)
    names = _confirm_names(request)
    if names is None:
        return JsonResponse(
            {"error": _("Send a list of fact names.")}, status=400
        )
    confirmed = variable_answer_confirm(identity=request.identity, names=names)
    return JsonResponse({"confirmed": confirmed})


def _confirm_names(request) -> list[str] | None:
    """The submitted fact names, or None when the body is malformed."""
    if request.content_type == "application/json":
        try:
            names = json.loads(request.body).get("names")
        except (json.JSONDecodeError, AttributeError):
            return None
    else:
        names = request.POST.getlist("names")
    if not isinstance(names, list) or not all(
        isinstance(name, str) for name in names
    ):
        return None
    return names


def csrf_failure(request, reason=""):
    """CSRF failures on the interview handoff fall back to the plain link.

    A litigant browsing with all cookies blocked never receives the CSRF
    cookie ``topic_flow_interview``'s form depends on, so the POST 403s in
    CsrfViewMiddleware before the view's own DocassembleError fallback ever
    runs — leaving no path to the interview at all. That failure mode hits
    privacy-hardened phones and locked-down shared/library machines hardest,
    which is the audience the handoff (#804) is for. Reroute those hits to
    the plain launch URL the view would have used; anything else keeps
    Django's default CSRF failure page.

    Wired app-wide via ``CSRF_FAILURE_VIEW`` since Django only supports one
    such hook, but it only special-cases this one route.
    """
    try:
        match = resolve(request.path)
    except Resolver404:
        match = None
    if match and match.url_name == "topic_flow_interview":
        kwargs = match.kwargs
        corpus = registry.get(kwargs["court"], kwargs["topic"], kwargs["role"])
        target = interview_target(corpus) if corpus else None
        launch_url = interview_launch_url(target[0]) if target else None
        if launch_url is not None:
            return redirect(launch_url)
    return _django_csrf_failure(request, reason=reason)
