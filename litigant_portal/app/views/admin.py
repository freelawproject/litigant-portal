import io
import json
import re
from functools import wraps

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import URLValidator, validate_email
from django.http import FileResponse, HttpRequest, JsonResponse
from django.utils.text import slugify
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit
from pypdf.errors import PyPdfError

from litigant_portal.app.models import (
    Contact,
    Resource,
    Site,
    Topic,
    TopicFlow,
    TopicFlowDeadline,
    TopicFlowField,
    TopicFlowFieldGroup,
    TopicFlowForm,
    TopicFlowLink,
)
from litigant_portal.app.models.choices import (
    BedrockModel,
    JurisdictionLevel,
    OpenAIModel,
    State,
)
from litigant_portal.app.selectors.library import (
    court_library_get,
    court_library_list,
    topic_library_get,
    topic_library_list,
)
from litigant_portal.app.selectors.site import (
    contact_get,
    contact_list,
    contact_name_taken,
    resource_get,
    resource_label_taken,
    resource_list,
    site_get,
)
from litigant_portal.app.selectors.topic_flow import (
    topic_flow_date_field_get,
    topic_flow_deadline_get,
    topic_flow_field_get,
    topic_flow_field_group_get,
    topic_flow_field_name_taken,
    topic_flow_form_get,
    topic_flow_get,
    topic_flow_link_get,
    topic_flow_slug_taken,
    topic_get,
    topic_list,
)
from litigant_portal.app.selectors.user import user_get, user_list
from litigant_portal.app.services.library import (
    court_library_apply,
    topic_flow_library_apply,
    topic_library_apply,
)
from litigant_portal.app.services.site import (
    contact_create,
    contact_delete,
    contact_move,
    contact_update,
    resource_create,
    resource_delete,
    resource_move,
    resource_update,
    site_court_details_update,
    site_models_update,
)
from litigant_portal.app.services.topic_flow import (
    topic_create,
    topic_delete,
    topic_flow_content_update,
    topic_flow_create,
    topic_flow_deadline_create,
    topic_flow_deadline_delete,
    topic_flow_deadline_move,
    topic_flow_deadline_update,
    topic_flow_delete,
    topic_flow_details_update,
    topic_flow_enabled_update,
    topic_flow_field_create,
    topic_flow_field_delete,
    topic_flow_field_group_change,
    topic_flow_field_group_create,
    topic_flow_field_group_delete,
    topic_flow_field_group_move,
    topic_flow_field_group_update,
    topic_flow_field_move,
    topic_flow_field_update,
    topic_flow_form_create,
    topic_flow_form_delete,
    topic_flow_form_fill,
    topic_flow_form_move,
    topic_flow_form_pdf_fields,
    topic_flow_form_update,
    topic_flow_link_create,
    topic_flow_link_delete,
    topic_flow_link_move,
    topic_flow_link_update,
    topic_flow_sample_values,
    topic_move,
    topic_update,
)
from litigant_portal.app.services.user import (
    user_admin_toggle,
    user_developer_toggle,
)

USERS_PER_PAGE = 20
FORM_PDF_MAX_BYTES = 10 * 1024 * 1024


def admin_access_required(view):
    """JSON guard: requires the ``app.manage_site`` permission (held by
    the Admins/Developers groups and, implicitly, superusers)."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.has_perm("app.manage_site"):
            return JsonResponse({"error": _("Forbidden")}, status=403)
        return view(request, *args, **kwargs)

    return wrapped


def developer_required(view):
    """JSON guard: requires ``app.manage_developers`` (held by the
    Developers group and, implicitly, superusers)."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.has_perm("app.manage_developers"):
            return JsonResponse({"error": _("Forbidden")}, status=403)
        return view(request, *args, **kwargs)

    return wrapped


def _json_body(request: HttpRequest) -> dict | None:
    """The request's JSON object body, or ``None`` when it isn't one."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _site_payload(site: Site) -> dict:
    return {
        "court_name": site.court_name,
        "jurisdiction_level": site.jurisdiction_level,
        "state": site.state,
        "official_url": site.official_url,
        "official_resources_url": site.official_resources_url,
        "fast_model": site.fast_model or "",
        "assistant_model": site.assistant_model or "",
    }


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
@admin_access_required
def site_view(request: HttpRequest) -> JsonResponse:
    """The site's settings for the admin settings tab."""
    try:
        return JsonResponse(_site_payload(site_get()))
    except Site.DoesNotExist:
        return JsonResponse({"error": _("Site not configured")}, status=404)


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def site_court_details_update_view(request: HttpRequest) -> JsonResponse:
    """Update the site's court detail fields."""
    court_name = (request.POST.get("court_name") or "").strip()
    jurisdiction_level = (request.POST.get("jurisdiction_level") or "").strip()
    if jurisdiction_level and jurisdiction_level not in (
        JurisdictionLevel.values
    ):
        return JsonResponse(
            {"error": _("Invalid jurisdiction level")}, status=400
        )
    state = (request.POST.get("state") or "").strip().upper()
    if state and state not in State.values:
        return JsonResponse(
            {"error": _("State must be a valid two-letter code")}, status=400
        )
    urls = {}
    validate_url = URLValidator(schemes=["http", "https"])
    for field in ("official_url", "official_resources_url"):
        url = (request.POST.get(field) or "").strip()
        if url:
            try:
                validate_url(url)
            except ValidationError:
                return JsonResponse({"error": _("Invalid URL")}, status=400)
        urls[field] = url
    try:
        site = site_get()
    except Site.DoesNotExist:
        return JsonResponse({"error": _("Site not configured")}, status=404)
    return JsonResponse(
        _site_payload(
            site_court_details_update(
                site=site,
                court_name=court_name,
                jurisdiction_level=jurisdiction_level,
                state=state,
                **urls,
            )
        )
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def site_models_update_view(request: HttpRequest) -> JsonResponse:
    """Update the site's AI model selections."""
    valid_models = set(OpenAIModel.values) | set(BedrockModel.values)
    ai_models = {}
    for field in ("fast_model", "assistant_model"):
        model = (request.POST.get(field) or "").strip()
        if model and model not in valid_models:
            return JsonResponse({"error": _("Invalid model")}, status=400)
        ai_models[field] = model
    try:
        site = site_get()
    except Site.DoesNotExist:
        return JsonResponse({"error": _("Site not configured")}, status=404)
    return JsonResponse(
        _site_payload(site_models_update(site=site, **ai_models))
    )


def _form_payload(form: TopicFlowForm) -> dict:
    return {
        "id": str(form.id),
        "slug": form.slug,
        "name": form.name,
        "file_name": form.file.name.rsplit("/", 1)[-1],
        "mappings": [
            {
                "id": str(m.id),
                "pdf_field": m.pdf_field,
                "template": m.template,
                "checked_when": m.checked_when,
            }
            for m in form.mappings.all()
        ],
    }


def _field_payload(f) -> dict:
    return {
        "id": str(f.id),
        "name": f.name,
        "label": f.label,
        "data_type": f.data_type,
        "required": f.required,
        "help_text": f.help_text,
        "default": f.default,
        "choices": f.choices,
    }


def _flow_payload(flow: TopicFlow) -> dict:
    return {
        "id": str(flow.id),
        "slug": flow.slug,
        "name": flow.name,
        "enabled": flow.enabled,
        "sections": [
            {"id": str(s.id), "heading": s.heading, "content": s.content}
            for s in flow.sections.all()
        ],
        # Flat list (the deadline modal's date-field options) and the
        # grouped interview shape (builder + library comparison).
        "fields": [_field_payload(f) for f in flow.fields],
        "field_groups": [
            {
                "id": str(g.id),
                "title": g.title,
                "description": g.description,
                "fields": [_field_payload(f) for f in g.fields.all()],
            }
            for g in flow.field_groups.all()
        ],
        "links": [
            {"id": str(li.id), "name": li.name, "url": li.url}
            for li in flow.links.all()
        ],
        "deadlines": [
            {
                "id": str(d.id),
                "label": d.label,
                "description": d.description,
                "offset_days": d.offset_days,
                "offset_from": d.offset_from.name,
            }
            for d in flow.deadlines.all()
        ],
        "forms": [_form_payload(f) for f in flow.forms.all()],
    }


def _topic_payload(topic: Topic) -> dict:
    return {
        "id": str(topic.id),
        "slug": topic.slug,
        "title": topic.title,
        "subtitle": topic.subtitle,
        "description": topic.description,
        "icon": topic.icon,
        "meta_description": topic.meta_description,
        "prompts": topic.prompts,
        "order": topic.order,
        "flows": [_flow_payload(f) for f in topic.flows.all()],
    }


def _topic_fields(request: HttpRequest) -> tuple[dict | None, str | None]:
    """Parse and validate the JSON body of a topic create/update.
    Returns ``(fields, None)`` or ``(None, error_message)``."""
    data = _json_body(request)
    if data is None:
        return None, _("Invalid JSON body")
    title = str(data.get("title") or "").strip()
    if not title:
        return None, _("Title is required")
    prompts = data.get("prompts") or []
    if not isinstance(prompts, list) or not all(
        isinstance(p, str) for p in prompts
    ):
        return None, _("Prompts must be a list of strings")
    return {
        "title": title,
        "subtitle": str(data.get("subtitle") or "").strip(),
        "description": str(data.get("description") or "").strip(),
        "icon": str(data.get("icon") or "").strip(),
        "meta_description": str(data.get("meta_description") or "").strip(),
        "prompts": [p.strip() for p in prompts if p.strip()],
    }, None


@require_GET
@ratelimit(key="ip", rate="120/m", method="GET", block=True)
@admin_access_required
def topic_list_view(request: HttpRequest) -> JsonResponse:
    """The topics for the knowledge base tab."""
    return JsonResponse({"topics": [_topic_payload(t) for t in topic_list()]})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_create_view(request: HttpRequest) -> JsonResponse:
    """Create a topic."""
    fields, error = _topic_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    return JsonResponse(_topic_payload(topic_create(**fields)))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_update_view(request: HttpRequest, topic_id) -> JsonResponse:
    """Update a topic's editable fields."""
    fields, error = _topic_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    try:
        topic = topic_get(topic_id=topic_id)
    except Topic.DoesNotExist:
        return JsonResponse({"error": _("Topic not found")}, status=404)
    return JsonResponse(_topic_payload(topic_update(topic=topic, **fields)))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_delete_view(request: HttpRequest, topic_id) -> JsonResponse:
    """Delete a topic."""
    try:
        topic = topic_get(topic_id=topic_id)
    except Topic.DoesNotExist:
        return JsonResponse({"error": _("Topic not found")}, status=404)
    topic_delete(topic=topic)
    return JsonResponse({"deleted": True, "id": str(topic_id)})


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@admin_access_required
def topic_move_view(request: HttpRequest, topic_id) -> JsonResponse:
    """Move a topic up or down; returns the refreshed ordered list."""
    direction = (request.POST.get("direction") or "").strip()
    if direction not in ("up", "down"):
        return JsonResponse({"error": _("Invalid direction")}, status=400)
    try:
        topic = topic_get(topic_id=topic_id)
    except Topic.DoesNotExist:
        return JsonResponse({"error": _("Topic not found")}, status=404)
    topic_move(topic=topic, direction=direction)
    return JsonResponse({"topics": [_topic_payload(t) for t in topic_list()]})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_create_view(request: HttpRequest, topic_id) -> JsonResponse:
    """Create a flow on a topic (the create-flow modal): name and slug
    only — everything else is added on the flow page afterwards."""
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": _("Invalid JSON body")}, status=400)
    slug = slugify(str(data.get("slug") or ""))[:64]
    if not slug:
        return JsonResponse({"error": _("Slug is required")}, status=400)
    name = str(data.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": _("Name is required")}, status=400)
    try:
        topic = topic_get(topic_id=topic_id)
    except Topic.DoesNotExist:
        return JsonResponse({"error": _("Topic not found")}, status=404)
    if topic_flow_slug_taken(topic=topic, slug=slug):
        return JsonResponse(
            {"error": _("A flow with this slug already exists on this topic")},
            status=400,
        )
    return JsonResponse(
        _flow_payload(topic_flow_create(topic=topic, slug=slug, name=name))
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_content_update_view(
    request: HttpRequest, flow_id
) -> JsonResponse:
    """Save just a flow's content sections (the content editor's Save).

    Deliberately independent of the full-flow save, which is being
    dismantled piecemeal.
    """
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": _("Invalid JSON body")}, status=400)
    sections = []
    for item in data.get("sections") or []:
        if not isinstance(item, dict):
            return JsonResponse({"error": _("Invalid section")}, status=400)
        heading = str(item.get("heading") or "").strip()
        if not heading:
            return JsonResponse(
                {"error": _("Every section needs a heading")}, status=400
            )
        sections.append(
            {"heading": heading, "content": str(item.get("content") or "")}
        )
    try:
        flow = topic_flow_get(flow_id=flow_id)
    except TopicFlow.DoesNotExist:
        return JsonResponse({"error": _("Flow not found")}, status=404)
    return JsonResponse(
        _flow_payload(topic_flow_content_update(flow=flow, sections=sections))
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_details_update_view(
    request: HttpRequest, flow_id
) -> JsonResponse:
    """Save a flow's name and slug (the flow page's inline form).

    Deliberately independent of the full-flow save, which is being
    dismantled piecemeal.
    """
    data = _json_body(request)
    if data is None:
        return JsonResponse({"error": _("Invalid JSON body")}, status=400)
    slug = slugify(str(data.get("slug") or ""))[:64]
    if not slug:
        return JsonResponse({"error": _("Slug is required")}, status=400)
    name = str(data.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": _("Name is required")}, status=400)
    try:
        flow = topic_flow_get(flow_id=flow_id)
    except TopicFlow.DoesNotExist:
        return JsonResponse({"error": _("Flow not found")}, status=404)
    if topic_flow_slug_taken(topic=flow.topic, slug=slug, exclude_id=flow.id):
        return JsonResponse(
            {"error": _("A flow with this slug already exists on this topic")},
            status=400,
        )
    return JsonResponse(
        _flow_payload(
            topic_flow_details_update(flow=flow, name=name, slug=slug)
        )
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_delete_view(request: HttpRequest, flow_id) -> JsonResponse:
    """Delete a flow (the flow page's danger button)."""
    try:
        flow = topic_flow_get(flow_id=flow_id)
    except TopicFlow.DoesNotExist:
        return JsonResponse({"error": _("Flow not found")}, status=404)
    topic_flow_delete(flow=flow)
    return JsonResponse({"deleted": True, "id": str(flow_id)})


def _deadline_fields(
    request: HttpRequest, flow: TopicFlow
) -> tuple[dict | None, str | None]:
    """Parse and validate the JSON body of a deadline create/update.
    ``offset_from`` arrives as a field name and resolves to the field."""
    data = _json_body(request)
    if data is None:
        return None, _("Invalid JSON body")
    label = str(data.get("label") or "").strip()
    if not label:
        return None, _("Label is required")
    try:
        offset_days = int(data.get("offset_days") or 0)
    except (TypeError, ValueError):
        return None, _("Offset must be a whole number of days")
    offset_from = str(data.get("offset_from") or "").strip()
    field = topic_flow_date_field_get(flow=flow, name=offset_from)
    if field is None:
        return None, _(
            "The deadline must count from one of the flow's date fields"
        )
    return {
        "label": label,
        "description": str(data.get("description") or "").strip(),
        "offset_days": offset_days,
        "offset_from": field,
    }, None


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_deadline_create_view(
    request: HttpRequest, flow_id
) -> JsonResponse:
    """Create a deadline on a flow (the flow page's deadline modal)."""
    try:
        flow = topic_flow_get(flow_id=flow_id)
    except TopicFlow.DoesNotExist:
        return JsonResponse({"error": _("Flow not found")}, status=404)
    fields, error = _deadline_fields(request, flow)
    if error:
        return JsonResponse({"error": error}, status=400)
    topic_flow_deadline_create(flow=flow, **fields)
    return JsonResponse(_flow_payload(flow))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_deadline_update_view(
    request: HttpRequest, deadline_id
) -> JsonResponse:
    """Update a deadline (the flow page's deadline modal)."""
    try:
        deadline = topic_flow_deadline_get(deadline_id=deadline_id)
    except TopicFlowDeadline.DoesNotExist:
        return JsonResponse({"error": _("Deadline not found")}, status=404)
    fields, error = _deadline_fields(request, deadline.flow)
    if error:
        return JsonResponse({"error": error}, status=400)
    topic_flow_deadline_update(deadline=deadline, **fields)
    return JsonResponse(_flow_payload(deadline.flow))


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@admin_access_required
def topic_flow_deadline_delete_view(
    request: HttpRequest, deadline_id
) -> JsonResponse:
    """Delete a deadline from a flow."""
    try:
        deadline = topic_flow_deadline_get(deadline_id=deadline_id)
    except TopicFlowDeadline.DoesNotExist:
        return JsonResponse({"error": _("Deadline not found")}, status=404)
    topic_flow_deadline_delete(deadline=deadline)
    return JsonResponse({"deleted": True, "id": str(deadline_id)})


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@admin_access_required
def topic_flow_deadline_move_view(
    request: HttpRequest, deadline_id
) -> JsonResponse:
    """Move a deadline up or down in its flow's display order."""
    direction = (request.POST.get("direction") or "").strip()
    if direction not in ("up", "down"):
        return JsonResponse({"error": _("Invalid direction")}, status=400)
    try:
        deadline = topic_flow_deadline_get(deadline_id=deadline_id)
    except TopicFlowDeadline.DoesNotExist:
        return JsonResponse({"error": _("Deadline not found")}, status=404)
    topic_flow_deadline_move(deadline=deadline, direction=direction)
    return JsonResponse(_flow_payload(deadline.flow))


FIELD_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _field_group_fields(
    request: HttpRequest,
) -> tuple[dict | None, str | None]:
    """Parse and validate the JSON body of a field-group create/update."""
    data = _json_body(request)
    if data is None:
        return None, _("Invalid JSON body")
    title = str(data.get("title") or "").strip()
    if not title:
        return None, _("Title is required")
    return {
        "title": title,
        "description": str(data.get("description") or "").strip(),
    }, None


def _field_fields(
    request: HttpRequest, flow: TopicFlow, *, exclude_id=None
) -> tuple[dict | None, str | None]:
    """Parse and validate the JSON body of a field create/update.

    Field names become answer keys and PDF-template variables, so they
    must be snake_case and unique within the flow. Choice fields need at
    least one choice; other types carry none.
    """
    data = _json_body(request)
    if data is None:
        return None, _("Invalid JSON body")
    name = str(data.get("name") or "").strip()
    if not FIELD_NAME_RE.match(name):
        return None, _(
            "Name must be lowercase letters, digits, and underscores, "
            "starting with a letter"
        )
    if topic_flow_field_name_taken(
        flow=flow, name=name, exclude_id=exclude_id
    ):
        return None, _("A field with this name already exists on this flow")
    data_type = str(data.get("data_type") or "text").strip()
    if data_type not in TopicFlowField.DataType.values:
        return None, _("Invalid data type")
    choices = []
    if data_type == TopicFlowField.DataType.CHOICE:
        for item in data.get("choices") or []:
            if not isinstance(item, dict):
                return None, _("Invalid choice")
            value = str(item.get("value") or "").strip()
            label = str(item.get("label") or value).strip()
            if value:
                choices.append({"value": value, "label": label})
        if not choices:
            return None, _("A choice field needs at least one choice")
    return {
        "name": name,
        "label": str(data.get("label") or "").strip(),
        "help_text": str(data.get("help_text") or "").strip(),
        "required": bool(data.get("required")),
        "data_type": data_type,
        "choices": choices,
        "default": str(data.get("default") or "").strip(),
    }, None


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_field_group_create_view(
    request: HttpRequest, flow_id
) -> JsonResponse:
    """Create an interview page on a flow (the builder's group modal)."""
    fields, error = _field_group_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    try:
        flow = topic_flow_get(flow_id=flow_id)
    except TopicFlow.DoesNotExist:
        return JsonResponse({"error": _("Flow not found")}, status=404)
    topic_flow_field_group_create(flow=flow, **fields)
    return JsonResponse(_flow_payload(flow))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_field_group_update_view(
    request: HttpRequest, group_id
) -> JsonResponse:
    """Update an interview page (the builder's group modal)."""
    fields, error = _field_group_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    try:
        group = topic_flow_field_group_get(group_id=group_id)
    except TopicFlowFieldGroup.DoesNotExist:
        return JsonResponse({"error": _("Group not found")}, status=404)
    topic_flow_field_group_update(group=group, **fields)
    return JsonResponse(_flow_payload(group.flow))


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@admin_access_required
def topic_flow_field_group_move_view(
    request: HttpRequest, group_id
) -> JsonResponse:
    """Move an interview page up or down in its flow."""
    direction = (request.POST.get("direction") or "").strip()
    if direction not in ("up", "down"):
        return JsonResponse({"error": _("Invalid direction")}, status=400)
    try:
        group = topic_flow_field_group_get(group_id=group_id)
    except TopicFlowFieldGroup.DoesNotExist:
        return JsonResponse({"error": _("Group not found")}, status=404)
    topic_flow_field_group_move(group=group, direction=direction)
    return JsonResponse(_flow_payload(group.flow))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_field_group_delete_view(
    request: HttpRequest, group_id
) -> JsonResponse:
    """Delete an interview page, its fields, and their saved answers."""
    try:
        group = topic_flow_field_group_get(group_id=group_id)
    except TopicFlowFieldGroup.DoesNotExist:
        return JsonResponse({"error": _("Group not found")}, status=404)
    flow = group.flow
    topic_flow_field_group_delete(group=group)
    return JsonResponse(_flow_payload(flow))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_field_create_view(
    request: HttpRequest, group_id
) -> JsonResponse:
    """Create a field on an interview page (the builder's field modal)."""
    try:
        group = topic_flow_field_group_get(group_id=group_id)
    except TopicFlowFieldGroup.DoesNotExist:
        return JsonResponse({"error": _("Group not found")}, status=404)
    fields, error = _field_fields(request, group.flow)
    if error:
        return JsonResponse({"error": error}, status=400)
    topic_flow_field_create(group=group, **fields)
    return JsonResponse(_flow_payload(group.flow))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_field_update_view(
    request: HttpRequest, field_id
) -> JsonResponse:
    """Update a field (the builder's field modal), optionally moving it
    to another of the flow's interview pages (``group_id``) — appended to
    that page's end."""
    try:
        field = topic_flow_field_get(field_id=field_id)
    except TopicFlowField.DoesNotExist:
        return JsonResponse({"error": _("Field not found")}, status=404)
    flow = field.group.flow
    fields, error = _field_fields(request, flow, exclude_id=field.id)
    if error:
        return JsonResponse({"error": error}, status=400)
    group_id = str((_json_body(request) or {}).get("group_id") or "").strip()
    target = None
    if group_id and group_id != str(field.group_id):
        try:
            target = topic_flow_field_group_get(group_id=group_id)
        except (TopicFlowFieldGroup.DoesNotExist, ValidationError):
            return JsonResponse({"error": _("Group not found")}, status=404)
        if target.flow_id != flow.id:
            return JsonResponse(
                {"error": _("Group belongs to a different flow")}, status=400
            )
    topic_flow_field_update(field=field, **fields)
    if target is not None:
        topic_flow_field_group_change(field=field, group=target)
    return JsonResponse(_flow_payload(flow))


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@admin_access_required
def topic_flow_field_move_view(request: HttpRequest, field_id) -> JsonResponse:
    """Move a field up or down within its interview page."""
    direction = (request.POST.get("direction") or "").strip()
    if direction not in ("up", "down"):
        return JsonResponse({"error": _("Invalid direction")}, status=400)
    try:
        field = topic_flow_field_get(field_id=field_id)
    except TopicFlowField.DoesNotExist:
        return JsonResponse({"error": _("Field not found")}, status=404)
    topic_flow_field_move(field=field, direction=direction)
    return JsonResponse(_flow_payload(field.group.flow))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_field_delete_view(
    request: HttpRequest, field_id
) -> JsonResponse:
    """Delete a field and its saved answers."""
    try:
        field = topic_flow_field_get(field_id=field_id)
    except TopicFlowField.DoesNotExist:
        return JsonResponse({"error": _("Field not found")}, status=404)
    flow = field.group.flow
    topic_flow_field_delete(field=field)
    return JsonResponse(_flow_payload(flow))


def _link_fields(request: HttpRequest) -> tuple[dict | None, str | None]:
    """Parse and validate the JSON body of a link create/update."""
    data = _json_body(request)
    if data is None:
        return None, _("Invalid JSON body")
    name = str(data.get("name") or "").strip()
    if not name:
        return None, _("Name is required")
    url = str(data.get("url") or "").strip()
    try:
        URLValidator(schemes=["http", "https"])(url)
    except ValidationError:
        return None, _("A valid URL is required")
    return {"name": name, "url": url}, None


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_link_create_view(request: HttpRequest, flow_id) -> JsonResponse:
    """Create a link on a flow (the flow page's link modal)."""
    fields, error = _link_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    try:
        flow = topic_flow_get(flow_id=flow_id)
    except TopicFlow.DoesNotExist:
        return JsonResponse({"error": _("Flow not found")}, status=404)
    topic_flow_link_create(flow=flow, **fields)
    return JsonResponse(_flow_payload(flow))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_link_update_view(request: HttpRequest, link_id) -> JsonResponse:
    """Update a link (the flow page's link modal)."""
    fields, error = _link_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    try:
        link = topic_flow_link_get(link_id=link_id)
    except TopicFlowLink.DoesNotExist:
        return JsonResponse({"error": _("Link not found")}, status=404)
    topic_flow_link_update(link=link, **fields)
    return JsonResponse(_flow_payload(link.flow))


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@admin_access_required
def topic_flow_link_delete_view(request: HttpRequest, link_id) -> JsonResponse:
    """Delete a link from a flow."""
    try:
        link = topic_flow_link_get(link_id=link_id)
    except TopicFlowLink.DoesNotExist:
        return JsonResponse({"error": _("Link not found")}, status=404)
    topic_flow_link_delete(link=link)
    return JsonResponse({"deleted": True, "id": str(link_id)})


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@admin_access_required
def topic_flow_link_move_view(request: HttpRequest, link_id) -> JsonResponse:
    """Move a link up or down in its flow's display order."""
    direction = (request.POST.get("direction") or "").strip()
    if direction not in ("up", "down"):
        return JsonResponse({"error": _("Invalid direction")}, status=400)
    try:
        link = topic_flow_link_get(link_id=link_id)
    except TopicFlowLink.DoesNotExist:
        return JsonResponse({"error": _("Link not found")}, status=404)
    topic_flow_link_move(link=link, direction=direction)
    return JsonResponse(_flow_payload(link.flow))


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@admin_access_required
def topic_flow_form_move_view(request: HttpRequest, form_id) -> JsonResponse:
    """Move a form up or down in its flow's display order."""
    direction = (request.POST.get("direction") or "").strip()
    if direction not in ("up", "down"):
        return JsonResponse({"error": _("Invalid direction")}, status=400)
    try:
        form = topic_flow_form_get(form_id=form_id)
    except TopicFlowForm.DoesNotExist:
        return JsonResponse({"error": _("Form not found")}, status=404)
    topic_flow_form_move(form=form, direction=direction)
    return JsonResponse(_flow_payload(form.flow))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_enabled_update_view(
    request: HttpRequest, flow_id
) -> JsonResponse:
    """Flip a flow between Draft and Live (the topic card's switch)."""
    data = _json_body(request)
    if data is None or not isinstance(data.get("enabled"), bool):
        return JsonResponse({"error": _("Invalid JSON body")}, status=400)
    try:
        flow = topic_flow_get(flow_id=flow_id)
    except TopicFlow.DoesNotExist:
        return JsonResponse({"error": _("Flow not found")}, status=404)
    return JsonResponse(
        _flow_payload(
            topic_flow_enabled_update(flow=flow, enabled=data["enabled"])
        )
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_form_create_view(request: HttpRequest, flow_id) -> JsonResponse:
    """Attach an uploaded fillable PDF form to a flow."""
    name = (request.POST.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": _("Name is required")}, status=400)
    upload = request.FILES.get("file")
    if upload is None:
        return JsonResponse({"error": _("A PDF file is required")}, status=400)
    if not (
        upload.name.lower().endswith(".pdf")
        and upload.content_type == "application/pdf"
    ):
        return JsonResponse({"error": _("File must be a PDF")}, status=400)
    if upload.size > FORM_PDF_MAX_BYTES:
        return JsonResponse(
            {"error": _("PDF must be 10MB or smaller")}, status=400
        )
    try:
        flow = topic_flow_get(flow_id=flow_id)
    except TopicFlow.DoesNotExist:
        return JsonResponse({"error": _("Flow not found")}, status=404)
    form = topic_flow_form_create(flow=flow, name=name, file=upload)
    try:
        pdf_fields = topic_flow_form_pdf_fields(form=form)
    except PyPdfError:
        topic_flow_form_delete(form=form)
        return JsonResponse(
            {"error": _("Could not read the PDF's form fields")}, status=400
        )
    return JsonResponse(
        {"form": _form_payload(form), "pdf_fields": pdf_fields}
    )


def _form_fields(request: HttpRequest) -> tuple[dict | None, str | None]:
    """Parse and validate the JSON body of a form editor save.
    Returns ``(fields, None)`` or ``(None, error_message)``."""
    data = _json_body(request)
    if data is None:
        return None, _("Invalid JSON body")
    name = str(data.get("name") or "").strip()
    if not name:
        return None, _("Name is required")
    mappings = []
    for item in data.get("mappings") or []:
        if not isinstance(item, dict):
            return None, _("Invalid mapping")
        pdf_field = str(item.get("pdf_field") or "").strip()
        if not pdf_field:
            return None, _("Every mapping needs a PDF field")
        mappings.append(
            {
                "pdf_field": pdf_field,
                "template": str(item.get("template") or ""),
                "checked_when": str(item.get("checked_when") or "").strip(),
            }
        )
    return {"name": name, "mappings": mappings}, None


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_form_update_view(request: HttpRequest, form_id) -> JsonResponse:
    """Save a form's name and field mappings from the form editor."""
    fields, error = _form_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    try:
        form = topic_flow_form_get(form_id=form_id)
    except TopicFlowForm.DoesNotExist:
        return JsonResponse({"error": _("Form not found")}, status=404)
    return JsonResponse(
        _form_payload(topic_flow_form_update(form=form, **fields))
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_flow_form_delete_view(request: HttpRequest, form_id) -> JsonResponse:
    """Delete a form from a flow."""
    try:
        form = topic_flow_form_get(form_id=form_id)
    except TopicFlowForm.DoesNotExist:
        return JsonResponse({"error": _("Form not found")}, status=404)
    topic_flow_form_delete(form=form)
    return JsonResponse({"deleted": True, "id": str(form_id)})


@require_GET
@ratelimit(key="ip", rate="30/m", method="GET", block=True)
@admin_access_required
def topic_flow_form_preview_view(request: HttpRequest, form_id):
    """The form filled with sample answers, for the admin preview."""
    try:
        form = topic_flow_form_get(form_id=form_id)
    except TopicFlowForm.DoesNotExist:
        return JsonResponse({"error": _("Form not found")}, status=404)
    filled = topic_flow_form_fill(
        form=form, values=topic_flow_sample_values(flow=form.flow)
    )
    return FileResponse(
        io.BytesIO(filled),
        content_type="application/pdf",
        filename=f"{form.slug}-preview.pdf",
    )


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
@admin_access_required
def library_topic_list_view(request: HttpRequest) -> JsonResponse:
    """Topic configs from the content library for the admin sidebar."""
    return JsonResponse({"topics": topic_library_list()})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def library_topic_apply_view(
    request: HttpRequest, court_slug: str, topic_slug: str
) -> JsonResponse:
    """Apply a full topic library config."""
    config = topic_library_get(court_slug=court_slug, topic_slug=topic_slug)
    if config is None:
        return JsonResponse(
            {"error": _("Configuration not found")}, status=404
        )
    topic_library_apply(config=config)
    return JsonResponse({"applied": True})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def library_topic_flow_apply_view(
    request: HttpRequest, court_slug: str, topic_slug: str, flow_slug: str
) -> JsonResponse:
    """Apply a single library flow (creating its topic from the config
    when it doesn't exist yet)."""
    config = topic_library_get(court_slug=court_slug, topic_slug=topic_slug)
    flow_config = config and next(
        (f for f in config["flows"] if f["slug"] == flow_slug), None
    )
    if flow_config is None:
        return JsonResponse(
            {"error": _("Configuration not found")}, status=404
        )
    topic_flow_library_apply(config=config, flow_config=flow_config)
    return JsonResponse({"applied": True})


def _contact_payload(contact: Contact) -> dict:
    return {
        "id": str(contact.id),
        "name": contact.name,
        "phone": contact.phone,
        "email": contact.email,
        "url": contact.url,
        "note": contact.note,
    }


def _contact_fields(request: HttpRequest) -> tuple[dict | None, str | None]:
    """Parse and validate the JSON body of a contact create/update.
    Returns ``(fields, None)`` or ``(None, error_message)``."""
    data = _json_body(request)
    if data is None:
        return None, _("Invalid JSON body")
    name = str(data.get("name") or "").strip()
    if not name:
        return None, _("Name is required")
    email = str(data.get("email") or "").strip()
    if email:
        try:
            validate_email(email)
        except ValidationError:
            return None, _("Invalid email")
    url = str(data.get("url") or "").strip()
    if url:
        try:
            URLValidator(schemes=["http", "https"])(url)
        except ValidationError:
            return None, _("Invalid URL")
    return {
        "name": name,
        "phone": str(data.get("phone") or "").strip(),
        "email": email,
        "url": url,
        "note": str(data.get("note") or "").strip(),
    }, None


@require_GET
@ratelimit(key="ip", rate="120/m", method="GET", block=True)
@admin_access_required
def contact_list_view(request: HttpRequest) -> JsonResponse:
    """The site's contacts for the admin settings tab."""
    return JsonResponse(
        {"contacts": [_contact_payload(c) for c in contact_list()]}
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def contact_create_view(request: HttpRequest) -> JsonResponse:
    """Create a contact."""
    fields, error = _contact_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    if contact_name_taken(name=fields["name"]):
        return JsonResponse(
            {"error": _("A contact with this name already exists")},
            status=400,
        )
    return JsonResponse(_contact_payload(contact_create(**fields)))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def contact_update_view(request: HttpRequest, contact_id) -> JsonResponse:
    """Update a contact's editable fields."""
    fields, error = _contact_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    try:
        contact = contact_get(contact_id=contact_id)
    except Contact.DoesNotExist:
        return JsonResponse({"error": _("Contact not found")}, status=404)
    if contact_name_taken(name=fields["name"], exclude_id=contact.id):
        return JsonResponse(
            {"error": _("A contact with this name already exists")},
            status=400,
        )
    return JsonResponse(
        _contact_payload(contact_update(contact=contact, **fields))
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def contact_delete_view(request: HttpRequest, contact_id) -> JsonResponse:
    """Delete a contact."""
    try:
        contact = contact_get(contact_id=contact_id)
    except Contact.DoesNotExist:
        return JsonResponse({"error": _("Contact not found")}, status=404)
    contact_delete(contact=contact)
    return JsonResponse({"deleted": True, "id": str(contact_id)})


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@admin_access_required
def contact_move_view(request: HttpRequest, contact_id) -> JsonResponse:
    """Move a contact up or down; returns the refreshed ordered list."""
    direction = (request.POST.get("direction") or "").strip()
    if direction not in ("up", "down"):
        return JsonResponse({"error": _("Invalid direction")}, status=400)
    try:
        contact = contact_get(contact_id=contact_id)
    except Contact.DoesNotExist:
        return JsonResponse({"error": _("Contact not found")}, status=404)
    contact_move(contact=contact, direction=direction)
    return JsonResponse(
        {"contacts": [_contact_payload(c) for c in contact_list()]}
    )


def _resource_payload(resource: Resource) -> dict:
    return {
        "id": str(resource.id),
        "label": resource.label,
        "url": resource.url,
        "note": resource.note,
    }


def _resource_fields(request: HttpRequest) -> tuple[dict | None, str | None]:
    """Parse and validate the JSON body of a resource create/update.
    Returns ``(fields, None)`` or ``(None, error_message)``."""
    data = _json_body(request)
    if data is None:
        return None, _("Invalid JSON body")
    label = str(data.get("label") or "").strip()
    if not label:
        return None, _("Label is required")
    url = str(data.get("url") or "").strip()
    if not url:
        return None, _("URL is required")
    try:
        URLValidator(schemes=["http", "https"])(url)
    except ValidationError:
        return None, _("Invalid URL")
    return {
        "label": label,
        "url": url,
        "note": str(data.get("note") or "").strip(),
    }, None


@require_GET
@ratelimit(key="ip", rate="120/m", method="GET", block=True)
@admin_access_required
def resource_list_view(request: HttpRequest) -> JsonResponse:
    """The site's resources for the admin settings tab."""
    return JsonResponse(
        {"resources": [_resource_payload(r) for r in resource_list()]}
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def resource_create_view(request: HttpRequest) -> JsonResponse:
    """Create a resource."""
    fields, error = _resource_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    if resource_label_taken(label=fields["label"]):
        return JsonResponse(
            {"error": _("A resource with this label already exists")},
            status=400,
        )
    return JsonResponse(_resource_payload(resource_create(**fields)))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def resource_update_view(request: HttpRequest, resource_id) -> JsonResponse:
    """Update a resource's editable fields."""
    fields, error = _resource_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    try:
        resource = resource_get(resource_id=resource_id)
    except Resource.DoesNotExist:
        return JsonResponse({"error": _("Resource not found")}, status=404)
    if resource_label_taken(label=fields["label"], exclude_id=resource.id):
        return JsonResponse(
            {"error": _("A resource with this label already exists")},
            status=400,
        )
    return JsonResponse(
        _resource_payload(resource_update(resource=resource, **fields))
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def resource_delete_view(request: HttpRequest, resource_id) -> JsonResponse:
    """Delete a resource."""
    try:
        resource = resource_get(resource_id=resource_id)
    except Resource.DoesNotExist:
        return JsonResponse({"error": _("Resource not found")}, status=404)
    resource_delete(resource=resource)
    return JsonResponse({"deleted": True, "id": str(resource_id)})


@require_POST
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
@admin_access_required
def resource_move_view(request: HttpRequest, resource_id) -> JsonResponse:
    """Move a resource up or down; returns the refreshed ordered list."""
    direction = (request.POST.get("direction") or "").strip()
    if direction not in ("up", "down"):
        return JsonResponse({"error": _("Invalid direction")}, status=400)
    try:
        resource = resource_get(resource_id=resource_id)
    except Resource.DoesNotExist:
        return JsonResponse({"error": _("Resource not found")}, status=404)
    resource_move(resource=resource, direction=direction)
    return JsonResponse(
        {"resources": [_resource_payload(r) for r in resource_list()]}
    )


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
@admin_access_required
def library_court_list_view(request: HttpRequest) -> JsonResponse:
    """Court configs from the content library for the admin sidebar."""
    return JsonResponse({"courts": court_library_list()})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def library_court_apply_view(request: HttpRequest, slug: str) -> JsonResponse:
    """Pre-populate the site from a court library config."""
    config = court_library_get(slug=slug)
    if config is None:
        return JsonResponse(
            {"error": _("Configuration not found")}, status=404
        )
    prune = (request.POST.get("prune") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    try:
        court_library_apply(config=config, prune=prune)
    except Site.DoesNotExist:
        return JsonResponse({"error": _("Site not configured")}, status=409)
    return JsonResponse({"applied": True, "slug": slug})


def _user_payload(user: User, *, viewer: User) -> dict:
    is_self = user.id == viewer.id
    return {
        "id": user.id,
        "email": user.email,
        "name": user.get_full_name(),
        "joined": user.date_joined.strftime("%Y-%m-%d"),
        "is_admin": getattr(user, "is_admin_member", False),
        "is_developer": getattr(user, "is_developer_member", False),
        "can_toggle_admin": (
            viewer.has_perm("app.manage_developers") or not is_self
        ),
        "can_toggle_developer": not is_self,
    }


@require_GET
@ratelimit(key="ip", rate="120/m", method="GET", block=True)
@admin_access_required
def user_list_view(request: HttpRequest) -> JsonResponse:
    """Paginated users for the admin users tab; ``q`` filters by email."""
    search = (request.GET.get("q") or "").strip()
    paginator = Paginator(user_list(search=search), USERS_PER_PAGE)
    page = paginator.get_page(request.GET.get("page"))
    return JsonResponse(
        {
            "users": [_user_payload(u, viewer=request.user) for u in page],
            "page": page.number,
            "num_pages": paginator.num_pages,
            "total": paginator.count,
        }
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def user_admin_toggle_view(request: HttpRequest, user_id: int) -> JsonResponse:
    """Toggle a user's Admins-group membership (admin access)."""
    try:
        target = user_get(user_id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": _("User not found")}, status=404)
    if target.id == request.user.id and not request.user.has_perm(
        "app.manage_developers"
    ):
        return JsonResponse(
            {"error": _("You can't change your own admin access")},
            status=403,
        )
    is_admin = user_admin_toggle(user=target)
    return JsonResponse({"id": target.id, "is_admin": is_admin})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@developer_required
def user_developer_toggle_view(
    request: HttpRequest, user_id: int
) -> JsonResponse:
    """Toggle a user's Developers-group membership."""
    try:
        target = user_get(user_id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": _("User not found")}, status=404)
    if target.id == request.user.id:
        return JsonResponse(
            {"error": _("You can't change your own developer status")},
            status=403,
        )
    return JsonResponse(
        {"id": target.id, "is_developer": user_developer_toggle(user=target)}
    )
