import json
import os
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.core.validators import URLValidator
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from litigant_portal.app.models import Site, Topic
from litigant_portal.app.models.choices import (
    BedrockModel,
    JurisdictionLevel,
    OpenAIModel,
    State,
    get_default_model,
)
from litigant_portal.app.selectors.admin import (
    site_get,
    site_get_active,
    site_list,
    topic_get,
    topic_list,
    user_list,
)
from litigant_portal.app.services.admin import (
    site_activate,
    site_membership_toggle,
    site_update,
    topic_create,
    topic_delete,
    topic_update,
    user_can_access_admin,
    user_developer_toggle,
)

USERS_PER_PAGE = 20


def admin_access_required(view):
    """JSON guard: developers (staff) or members of the active site."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not user_can_access_admin(user=request.user):
            return JsonResponse({"error": _("Forbidden")}, status=403)
        return view(request, *args, **kwargs)

    return wrapped


def staff_required(view):
    """JSON guard: developers (staff) only."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_staff:
            return JsonResponse({"error": _("Forbidden")}, status=403)
        return view(request, *args, **kwargs)

    return wrapped


@login_required
def dashboard(request: HttpRequest) -> HttpResponse:
    """Admin dashboard shell — developers or active-site members only."""
    if not user_can_access_admin(user=request.user):
        raise PermissionDenied
    openai_available = bool(os.environ.get("OPENAI_API_KEY"))
    bedrock_available = bool(os.environ.get("AWS_BEARER_TOKEN_BEDROCK"))
    model_choice_groups = []
    if openai_available:
        model_choice_groups.append(("OpenAI", OpenAIModel.choices))
    if bedrock_available or not openai_available:
        model_choice_groups.append(("AWS Bedrock", BedrockModel.choices))
    all_model_labels = dict(OpenAIModel.choices) | dict(BedrockModel.choices)
    return render(
        request,
        "v2/admin/index.html",
        {
            "openai_available": openai_available,
            "bedrock_available": bedrock_available,
            "model_choice_groups": model_choice_groups,
            "default_model_label": all_model_labels[get_default_model()],
            "jurisdiction_choices": JurisdictionLevel.choices,
            "state_choices": State.choices,
        },
    )


def _site_payload(site: Site) -> dict:
    return {
        "id": str(site.id),
        "name": site.name,
        "active": site.active,
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
def site_list_view(request: HttpRequest) -> JsonResponse:
    """All site settings rows for the admin settings tab."""
    return JsonResponse({"sites": [_site_payload(s) for s in site_list()]})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def site_update_view(request: HttpRequest, site_id) -> JsonResponse:
    """Update a site row's editable fields."""
    name = (request.POST.get("name") or "").strip()
    if not name:
        return JsonResponse({"error": _("Name is required")}, status=400)
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
    valid_models = set(OpenAIModel.values) | set(BedrockModel.values)
    ai_models = {}
    for field in ("fast_model", "assistant_model"):
        model = (request.POST.get(field) or "").strip()
        if model and model not in valid_models:
            return JsonResponse({"error": _("Invalid model")}, status=400)
        ai_models[field] = model
    try:
        site = site_get(site_id=site_id)
    except Site.DoesNotExist:
        return JsonResponse({"error": _("Site not found")}, status=404)
    return JsonResponse(
        _site_payload(
            site_update(
                site=site,
                name=name,
                court_name=court_name,
                jurisdiction_level=jurisdiction_level,
                state=state,
                **urls,
                **ai_models,
            )
        )
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@staff_required
def site_activate_view(request: HttpRequest, site_id) -> JsonResponse:
    """Make a site row the single active one. Developers only."""
    try:
        site = site_get(site_id=site_id)
    except Site.DoesNotExist:
        return JsonResponse({"error": _("Site not found")}, status=404)
    return JsonResponse(_site_payload(site_activate(site=site)))


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
    }


def _topic_fields(request: HttpRequest) -> tuple[dict | None, str | None]:
    """Parse and validate the JSON body of a topic create/update.
    Returns ``(fields, None)`` or ``(None, error_message)``."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        data = None
    if not isinstance(data, dict):
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
    """The active site's topics for the knowledge base tab."""
    try:
        site = site_get_active()
    except Site.DoesNotExist:
        return JsonResponse({"topics": []})
    return JsonResponse(
        {"topics": [_topic_payload(t) for t in topic_list(site=site)]}
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_create_view(request: HttpRequest) -> JsonResponse:
    """Create a topic in the active site."""
    fields, error = _topic_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    try:
        site = site_get_active()
    except Site.DoesNotExist:
        return JsonResponse({"error": _("No active site")}, status=409)
    return JsonResponse(_topic_payload(topic_create(site=site, **fields)))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_update_view(request: HttpRequest, topic_id) -> JsonResponse:
    """Update a topic's editable fields."""
    fields, error = _topic_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    try:
        topic = topic_get(site=site_get_active(), topic_id=topic_id)
    except (Site.DoesNotExist, Topic.DoesNotExist):
        return JsonResponse({"error": _("Topic not found")}, status=404)
    return JsonResponse(_topic_payload(topic_update(topic=topic, **fields)))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@admin_access_required
def topic_delete_view(request: HttpRequest, topic_id) -> JsonResponse:
    """Delete a topic from the active site."""
    try:
        topic = topic_get(site=site_get_active(), topic_id=topic_id)
    except (Site.DoesNotExist, Topic.DoesNotExist):
        return JsonResponse({"error": _("Topic not found")}, status=404)
    topic_delete(topic=topic)
    return JsonResponse({"deleted": True, "id": str(topic_id)})


def _user_payload(user: User, *, viewer: User) -> dict:
    is_self = user.id == viewer.id
    return {
        "id": user.id,
        "email": user.email,
        "name": user.get_full_name(),
        "joined": user.date_joined.strftime("%Y-%m-%d"),
        "is_admin": getattr(user, "is_site_member", False),
        "is_staff": user.is_staff,
        "can_toggle_admin": viewer.is_staff or not is_self,
        "can_toggle_developer": not is_self,
    }


@require_GET
@ratelimit(key="ip", rate="120/m", method="GET", block=True)
@admin_access_required
def user_list_view(request: HttpRequest) -> JsonResponse:
    """Paginated users for the admin users tab; ``q`` filters by email."""
    search = (request.GET.get("q") or "").strip()
    try:
        site = site_get_active()
    except Site.DoesNotExist:
        site = None
    paginator = Paginator(user_list(search=search, site=site), USERS_PER_PAGE)
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
    """Toggle a user's membership (admin access) in the active site."""
    try:
        target = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": _("User not found")}, status=404)
    if target.id == request.user.id and not request.user.is_staff:
        return JsonResponse(
            {"error": _("You can't change your own admin access")},
            status=403,
        )
    try:
        site = site_get_active()
    except Site.DoesNotExist:
        return JsonResponse({"error": _("No active site")}, status=409)
    is_admin = site_membership_toggle(user=target, site=site)
    return JsonResponse({"id": target.id, "is_admin": is_admin})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@staff_required
def user_developer_toggle_view(
    request: HttpRequest, user_id: int
) -> JsonResponse:
    """Toggle a user's developer (staff) flag."""
    try:
        target = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({"error": _("User not found")}, status=404)
    if target.id == request.user.id:
        return JsonResponse(
            {"error": _("You can't change your own developer status")},
            status=403,
        )
    return JsonResponse(
        {"id": target.id, "is_staff": user_developer_toggle(user=target)}
    )
