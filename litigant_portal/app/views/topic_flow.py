import io
import json
from datetime import date, datetime

from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    JsonResponse,
)
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from litigant_portal.app.models import TopicFlow, TopicFlowField
from litigant_portal.app.selectors.topic_flow import (
    topic_flow_answer_values,
    topic_flow_get_public,
)
from litigant_portal.app.services.site import contact_list_vcf
from litigant_portal.app.services.topic_flow import (
    topic_flow_answers_update,
    topic_flow_calendar_ics,
    topic_flow_deadline_rows,
    topic_flow_field_value,
    topic_flow_form_fill,
    topic_flow_packet,
    topic_flow_progress,
)


def _topic_flow(topic_slug: str, flow_slug: str) -> TopicFlow:
    """Resolve a flow by slugs; Http404 on a miss."""
    try:
        return topic_flow_get_public(
            topic_slug=topic_slug, flow_slug=flow_slug
        )
    except TopicFlow.DoesNotExist:
        raise Http404(f"No Topic Flow {topic_slug}/{flow_slug}")


def _datetime_local(raw) -> str:
    """A stored datetime answer in the format ``datetime-local`` accepts."""
    try:
        return datetime.fromisoformat(str(raw)).strftime("%Y-%m-%dT%H:%M")
    except (TypeError, ValueError):
        return ""


def _interview_field(field: TopicFlowField, values: dict) -> dict:
    """One interview field as JSON for the client."""
    raw = values.get(field.name, field.default)
    value = topic_flow_field_value(field=field, raw=raw)
    if field.data_type == TopicFlowField.DataType.BOOLEAN:
        # None means "never answered" — kept distinct from False so the
        # client neither counts untouched checkboxes as answered nor saves
        # phantom False rows for them (posting null deletes, a no-op).
        value = None if value is None else bool(value)
    elif field.data_type == TopicFlowField.DataType.DATETIME:
        value = _datetime_local(raw)
    elif isinstance(value, date):
        value = value.isoformat()
    elif value is None:
        value = ""
    return {
        "name": field.name,
        "label": field.label or field.name,
        "helpText": field.help_text,
        "dataType": field.data_type,
        "required": field.required,
        "choices": field.choices,
        "value": value,
        # Whether an answer is actually stored. Distinct from value, which
        # merges in authored defaults so they prefill the wizard's inputs:
        # a default is a suggestion, not progress.
        "answered": field.name in values,
    }


def _interview_payload(flow: TopicFlow, values: dict) -> dict:
    """The flow's interview as steps, one per field group, in order."""
    steps = []
    for group in flow.field_groups.all():
        fields = [_interview_field(f, values) for f in group.fields.all()]
        if not fields:
            continue
        steps.append(
            {
                "title": group.title,
                "description": group.description,
                "fields": fields,
            }
        )
    return {"steps": steps}


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def topic_flow_interview_view(
    request: HttpRequest, topic_slug: str, flow_slug: str
) -> JsonResponse:
    """The flow's interview, with the identity's answers merged in."""
    flow = _topic_flow(topic_slug, flow_slug)
    values = topic_flow_answer_values(identity=request.identity, flow=flow)
    return JsonResponse(_interview_payload(flow, values))


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
def topic_flow_answers_view(
    request: HttpRequest, topic_slug: str, flow_slug: str
) -> JsonResponse:
    """Store the identity's answers for a flow; returns the current values
    and the recomputed deadlines."""
    flow = _topic_flow(topic_slug, flow_slug)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = None
    answers = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(answers, dict):
        return JsonResponse({"error": _("Invalid JSON body")}, status=400)
    try:
        values = topic_flow_answers_update(
            identity=request.identity,
            flow=flow,
            answers=answers,
            reviewed=True,
        )
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)
    return JsonResponse(
        {
            "answers": values,
            "deadlines": [
                {
                    "label": row["label"],
                    "description": row["description"],
                    "date": row["date"].isoformat() if row["date"] else None,
                }
                for row in topic_flow_deadline_rows(flow=flow, values=values)
            ],
        }
    )


def topic_flow_summary_payload(*, flow: TopicFlow, identity) -> dict:
    """The flow's live status for a briefcase card: interview progress
    plus its forms and download links, computed for ``identity``."""
    values = topic_flow_answer_values(identity=identity, flow=flow)
    answered, total = topic_flow_progress(flow=flow, values=values)
    slugs = {"topic_slug": flow.topic.slug, "flow_slug": flow.slug}
    forms = [
        {
            "slug": form.slug,
            "name": form.name,
            "url": reverse(
                "topic_flow_api:form",
                kwargs={**slugs, "form_slug": form.slug},
            ),
        }
        for form in flow.forms.all()
    ]
    return {
        "topic_title": flow.topic.title,
        "name": flow.name,
        "url": reverse("pages:topic_flow", kwargs=slugs),
        "progress": {
            "answered": answered,
            "total": total,
            "label": _("%(answered)d of %(total)d answered")
            % {"answered": answered, "total": total},
        },
        "forms": forms,
        "packet_url": (
            reverse("topic_flow_api:packet", kwargs=slugs) if forms else None
        ),
    }


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def topic_flow_summary_view(
    request: HttpRequest, topic_slug: str, flow_slug: str
) -> JsonResponse:
    """The requester's own live status for a flow (chat briefcase card)."""
    flow = _topic_flow(topic_slug, flow_slug)
    return JsonResponse(
        topic_flow_summary_payload(flow=flow, identity=request.identity)
    )


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def topic_flow_packet_view(
    request: HttpRequest, topic_slug: str, flow_slug: str
) -> FileResponse:
    """Every flow form filled with the identity's answers, as one PDF."""
    flow = _topic_flow(topic_slug, flow_slug)
    if not flow.forms.all():
        raise Http404("Flow has no forms")
    values = topic_flow_answer_values(identity=request.identity, flow=flow)
    return FileResponse(
        io.BytesIO(topic_flow_packet(flow=flow, values=values)),
        as_attachment=True,
        filename=f"{flow.slug}-packet.pdf",
        content_type="application/pdf",
    )


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def topic_flow_form_view(
    request: HttpRequest, topic_slug: str, flow_slug: str, form_slug: str
) -> FileResponse:
    """A single flow form filled with the identity's answers."""
    flow = _topic_flow(topic_slug, flow_slug)
    form = next((f for f in flow.forms.all() if f.slug == form_slug), None)
    if form is None:
        raise Http404(f"No form {form_slug!r}")
    values = topic_flow_answer_values(identity=request.identity, flow=flow)
    return FileResponse(
        io.BytesIO(topic_flow_form_fill(form=form, values=values, flow=flow)),
        as_attachment=True,
        filename=f"{form.slug}.pdf",
        content_type="application/pdf",
    )


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def topic_flow_calendar_view(
    request: HttpRequest, topic_slug: str, flow_slug: str
) -> HttpResponse:
    """The flow's computed deadlines as a ``.ics`` calendar download."""
    flow = _topic_flow(topic_slug, flow_slug)
    values = topic_flow_answer_values(identity=request.identity, flow=flow)
    response = HttpResponse(
        topic_flow_calendar_ics(flow=flow, values=values),
        content_type="text/calendar; charset=utf-8",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{flow.slug}-deadlines.ics"'
    )
    return response


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def topic_flow_contacts_view(
    request: HttpRequest, topic_slug: str, flow_slug: str
) -> HttpResponse:
    """The site's contacts as a ``.vcf`` vCard download."""
    _topic_flow(topic_slug, flow_slug)
    response = HttpResponse(
        contact_list_vcf(),
        content_type="text/vcard; charset=utf-8",
    )
    response["Content-Disposition"] = 'attachment; filename="contacts.vcf"'
    return response
