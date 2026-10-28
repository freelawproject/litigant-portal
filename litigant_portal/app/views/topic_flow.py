import logging

from django.contrib import messages
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.csrf import csrf_failure as _django_csrf_failure
from django.views.decorators.http import require_POST

from litigant_portal.app.selectors.site import contact_list, resource_list
from litigant_portal.app.selectors.topic_flow import (
    variable_answer_unreviewed_names,
)
from litigant_portal.app.services.docassemble import (
    DocassembleError,
    docassemble_session_create,
    interview_launch_url,
)
from litigant_portal.app.services.topic_flow import (
    variable_answer_confirm,
    variable_answer_set_many,
)
from litigant_portal.app.topic_flow import rows
from litigant_portal.app.topic_flow.contacts import contact_dicts
from litigant_portal.app.topic_flow.downloads import ics_artifact, vcf_artifact
from litigant_portal.app.topic_flow.prefill import (
    flow_interview_target,
    prefill_variables,
)
from litigant_portal.app.views.utils import (
    briefcase_answers,
    has_identity,
    topic_flow_reviewed_answers,
    topic_flow_row_answers,
    topic_flow_row_cleared_names,
    topic_flow_row_get,
)

logger = logging.getLogger(__name__)


def topic_flow(request, court, topic, role):
    """The guided page at /t/{court}/{topic}/{role}/, built from the TopicFlow
    rows ``sync_corpus`` writes (404 on miss).

    GET renders the flow's layout with the visitor's stored answers, so the
    interview fields prefill. POST persists the submitted answers as
    VariableAnswer rows and redirects (PRG) so a reload re-GETs rather than
    re-submits; the whole flow works with JS off. The view stays thin: the
    row-to-section work lives in rows.py, deadline math in deadlines.py.

    Saving marks answers ``reviewed=True``: this page is where a human
    confirms what the assistant guessed, and only reviewed answers may
    reach the docassemble prefill.
    """
    flow = topic_flow_row_get(court, topic, role)
    sections = list(flow.sections.all())
    pages = rows.flow_pages(flow)
    form_conditions = list(flow.form_conditions.all())
    deadlines = list(flow.deadlines.all())
    names = rows.flow_variable_names(pages, form_conditions, deadlines)
    answers = topic_flow_row_answers(request, names)
    cleared = topic_flow_row_cleared_names(request, names)
    # The output blocks' rows (the URL's court's whole contact and resource
    # lists, not a per-flow pick) and the URL parts their links need.
    block_rows = {
        "form_conditions": form_conditions,
        "deadlines": deadlines,
        "contacts": contact_list(court=court),
        "resources": resource_list(court=court),
        "court": court,
        "topic": topic,
        "role": role,
    }

    if request.method == "POST":
        # Only currently asked variables are read, so a gated field whose
        # gate is unmet is ignored even if posted. A stored private field
        # renders blank, so a blank there is "keep", not "missing".
        variables = {v.name: v for _page, placed in pages for v in placed}
        asked = rows.asked_names(pages, answers)
        private = rows.private_names(pages)
        keep = {n for n in asked if n in private and n in answers}
        submitted, errors, valid = _accepted_answers(
            request.POST,
            asked,
            lambda s: rows.validate_answers(variables.values(), s, keep),
            lambda name, raw: rows.coerce_value(variables[name], raw),
            private,
        )
        # An untouched field re-saves its stored value, not the form's
        # narrower string of it (a datetime's zone, a float's type).
        valid = rows.restore_unchanged(variables, submitted, answers, valid)
        # A gated answer whose gate stops matching is cleared with the save,
        # so the briefcase and the prefill agree with the page.
        for name in rows.stale_gated_names(pages, answers, valid):
            valid[name] = None
        revealed = []
        if valid:
            variable_answer_set_many(
                identity=request.identity, values=valid, reviewed=True
            )
            # Re-read: a gate just saved decides which fields show next,
            # and the ones it uncovered get the toast and the anchor.
            answers = topic_flow_row_answers(request, names)
            cleared = topic_flow_row_cleared_names(request, names)
            asked_after = rows.asked_names(pages, answers)
            revealed = [name for name in asked_after if name not in asked]
            # A gate flipped by this save hides its dependents, so an error
            # on one has no field to land on: drop it rather than re-render
            # a page that shows no message.
            errors = {
                name: found
                for name, found in errors.items()
                if name in asked_after
            }
        if errors:
            # Soft-gate: re-render in place (no PRG) with inline errors so the
            # litigant can fix and resubmit. Render from the stored answers
            # (not the raw submission), so a rejected value can't leak into
            # the page while the form flags it.
            return _render_flow_page(
                request,
                flow.name,
                rows.render_flow(
                    flow,
                    sections,
                    pages,
                    answers,
                    errors,
                    cleared,
                    **block_rows,
                ),
            )
        if valid:
            _flash_saved(request, valid, private, revealed)
        # PRG back to the place just saved so the litigant keeps their place
        # and sees the recomputed deadlines, instead of the browser jumping
        # to the top of the page on the redirected GET.
        url = reverse(
            "pages:topic_flow",
            kwargs={"court": court, "topic": topic, "role": role},
        )
        # Field ids are variable names, so landing on the first revealed
        # question puts focus in it; otherwise back to the section saved.
        anchor = (
            revealed[0]
            if revealed
            else rows.submitted_section_anchor(pages, submitted)
        )
        if anchor:
            url = f"{url}#{anchor}"
        return redirect(url)

    return _render_flow_page(
        request,
        flow.name,
        rows.render_flow(
            flow, sections, pages, answers, cleared=cleared, **block_rows
        ),
    )


def _accepted_answers(post, names, validate, coerce, protected):
    """``(submitted, errors, valid)`` for a fact form POST.

    ``submitted`` is the posted strings for ``names``; ``errors`` is
    ``{name: [message]}``; ``valid`` is the typed values to store.
    ``protected`` names the fields that render blank even when stored (the
    glossary's private flag): a blank one is skipped unless its clear
    checkbox was posted (a blank there means "not shown", not "erase").
    """
    submitted = {name: post[name] for name in names if name in post}
    errors = validate(submitted)
    valid = {}
    for name, raw in submitted.items():
        if name in errors:
            continue
        value = coerce(name, raw)
        if (
            value is None
            and name in protected
            and f"{name}__clear" not in post
        ):
            continue
        valid[name] = value
    return submitted, errors, valid


def _flash_saved(request, valid, protected, revealed=()):
    """The toast after a save. A ``protected`` field re-renders blank even
    after a successful save, so without the longer message the save looks
    like it failed (#803). ``revealed`` names the questions the save
    uncovered, so a screen reader hears that the page is not done (WCAG
    4.1.3); a gate can reveal a question on an earlier page, so the toast
    does not say where."""
    private = any(valid.get(name) for name in protected)
    if revealed and private:
        text = _(
            "Saved. More questions appeared on this page. For your privacy, "
            "your answers are not shown here."
        )
    elif revealed:
        text = _("Saved. More questions appeared on this page.")
    elif private:
        text = _(
            "Saved. For your privacy, your answers are not shown on this page."
        )
    else:
        text = _("Saved.")
    messages.success(request, text)


def _render_flow_page(request, page_title, rendered_sections, **extra):
    """Render ``pages/topic_flow.html`` from an ordered ``RenderedSection``
    list."""
    briefcase_groups = briefcase_answers(request)
    evidence_by_name = {
        answer.variable.name: answer.evidence
        for group in briefcase_groups
        for answer in group["answers"]
        if not answer.reviewed and not answer.variable.is_private
    }
    for section in rendered_sections:
        for question in section.context.get("questions", ()):
            evidence = evidence_by_name.get(question["id"])
            if evidence and evidence.get("quote"):
                prefix = (
                    _("From your document:")
                    if evidence.get("upload_id")
                    else _("Because you said:")
                )
                question["help_text"] = (
                    f"{question['help_text']} {prefix} {evidence['quote']}"
                ).strip()
    section_links = [
        {"anchor": section.anchor_id, "heading": section.heading}
        for section in rendered_sections
        if section.heading
    ]
    return render(
        request,
        "pages/topic_flow.html",
        {
            "page_title": page_title,
            "rendered_sections": rendered_sections,
            "section_links": section_links,
            "frame_left_label": _("Sections"),
            "frame_left_icon": "list-bullet",
            "briefcase_groups": briefcase_groups,
            **extra,
        },
    )


def topic_flow_download(request, court, topic, role, output_id):
    """Download a Topic Flow output block as a file (e.g. an ``.ics``).

    The endpoint counterpart to the ``topic_flow`` render above: the output
    ids are the layout block names, and the file is built from the same rows
    and stored answers the page renders, so the download matches what's on
    screen (#1017). An unknown id or flow is 404.
    """
    artifact = _row_download(request, court, topic, role, output_id)
    response = HttpResponse(artifact.body, content_type=artifact.content_type)
    response["Content-Disposition"] = (
        f'attachment; filename="{artifact.filename}"'
    )
    return response


def _row_download(request, court, topic, role, output_id):
    """The ``calendar`` block as a ``.ics`` from the flow's deadline rows and
    the visitor's stored answers, or the ``contacts`` block as a ``.vcf``
    from the URL's court's Contact rows. Any other id is 404. The UID
    segment is the block name."""
    flow = topic_flow_row_get(court, topic, role, graph=False)
    uid_prefix = f"{court}-{topic}-{role}-{output_id}"
    if output_id == "calendar":
        deadlines = list(flow.deadlines.select_related("offset_from"))
        names = rows.flow_variable_names([], deadlines=deadlines)
        return ics_artifact(
            rows.flow_deadlines(
                deadlines, topic_flow_row_answers(request, names)
            ),
            uid_prefix=uid_prefix,
            filename="calendar.ics",
        )
    if output_id == "contacts":
        return vcf_artifact(
            contact_dicts(contact_list(court=court), id_attr="ref"),
            uid_prefix=uid_prefix,
            filename="contacts.vcf",
        )
    raise Http404(f"No downloadable output {output_id!r}")


@require_POST
def topic_flow_interview(request, court, topic, role):
    """Start a prefilled docassemble session and send the litigant to it.

    POST because creating the session is a side effect. Only reviewed answers
    are sent: a prefilled variable skips its interview question, so docassemble
    never asks the litigant to confirm it.

    Any failure redirects to the plain interview link instead. Unprefilled is a
    worse handoff than prefilled, but a dead button is worse than both.
    """
    target = _interview_target(court, topic, role)
    if target is None:
        raise Http404(f"No interview handoff for {court}/{topic}/{role}")
    return _interview_redirect(request, court, topic, role, target)


def _interview_target(court, topic, role):
    """``(interview, mapping)`` from the TopicFlow row at this URL, or None
    without a handoff. 404 for a flow that does not exist."""
    return flow_interview_target(
        topic_flow_row_get(court, topic, role, graph=False)
    )


def _interview_redirect(request, court, topic, role, target):
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

    Deliberately NOT an agent tool and not under ``/api/agents/``: only a
    human action may set ``reviewed=True``, because reviewed answers
    prefill the docassemble interview and skip their questions there. This
    stays a session-authenticated, CSRF-protected page endpoint the model
    cannot reach.

    Form-encoded only, with a repeated ``names`` field, an aware ISO
    ``as_of`` (when the card read the answers it shows) and the token in
    the body: the ``X-CSRFToken`` header does not survive the QA proxy
    (#940). Responds ``{"confirmed": n, "pending": [names]}``: ``pending``
    lists the named answers still unconfirmed afterwards, so the card can
    tell a value that changed since it was shown from one already confirmed
    on an earlier card (both leave ``n`` short).
    """
    if not has_identity(request):
        return JsonResponse({"error": _("Forbidden")}, status=403)
    names = [name for name in request.POST.getlist("names") if name]
    if not names:
        return JsonResponse(
            {"error": _("Send a list of fact names.")}, status=400
        )
    as_of = parse_datetime(request.POST.get("as_of", ""))
    if as_of is None or timezone.is_naive(as_of):
        return JsonResponse(
            {"error": _("Send when the answers were shown, as_of.")},
            status=400,
        )
    confirmed = variable_answer_confirm(
        identity=request.identity, names=names, as_of=as_of
    )
    pending = variable_answer_unreviewed_names(
        identity=request.identity, names=names
    )
    return JsonResponse({"confirmed": confirmed, "pending": pending})


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
        try:
            target = _interview_target(**match.kwargs)
        except Http404:
            target = None
        launch_url = interview_launch_url(target[0]) if target else None
        if launch_url is not None:
            return redirect(launch_url)
    return _django_csrf_failure(request, reason=reason)
