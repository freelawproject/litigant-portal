import json

from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.core.validators import URLValidator, validate_email
from django.http import HttpRequest, JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from litigant_portal.app.models import Site, Topic
from litigant_portal.app.models.choices import (
    BedrockModel,
    JurisdictionLevel,
    State,
)
from litigant_portal.app.selectors.site import site_get
from litigant_portal.app.selectors.topic_flow import topic_get, topic_list
from litigant_portal.app.selectors.user import (
    user_email_taken,
    user_get,
    user_is_manageable,
    user_list,
)
from litigant_portal.app.services.site import site_update
from litigant_portal.app.services.topic_flow import (
    topic_create,
    topic_delete,
    topic_update,
)
from litigant_portal.app.services.user import (
    user_active_set,
    user_admin_toggle,
    user_create,
    user_delete,
    user_developer_toggle,
    user_password_set,
    user_user_admin_toggle,
)
from litigant_portal.app.views.utils import (
    app_user_admin_required,
    can_manage_app_users,
    manage_developers_required,
    manage_site_required,
)

USERS_PER_PAGE = 20


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
@manage_site_required
def site_view(request: HttpRequest) -> JsonResponse:
    """The site's settings for the admin settings tab."""
    return JsonResponse(_site_payload(site_get()))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@manage_site_required
def site_update_view(request: HttpRequest) -> JsonResponse:
    """Update the site's editable fields."""
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
    ai_models = {}
    for field in ("fast_model", "assistant_model"):
        model = (request.POST.get(field) or "").strip()
        if model and model not in BedrockModel.values:
            return JsonResponse({"error": _("Invalid model")}, status=400)
        ai_models[field] = model
    return JsonResponse(
        _site_payload(
            site_update(
                court_name=court_name,
                jurisdiction_level=jurisdiction_level,
                state=state,
                **urls,
                **ai_models,
            )
        )
    )


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
@manage_site_required
def topic_list_view(request: HttpRequest) -> JsonResponse:
    """Topics for the knowledge base tab."""
    return JsonResponse({"topics": [_topic_payload(t) for t in topic_list()]})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@manage_site_required
def topic_create_view(request: HttpRequest) -> JsonResponse:
    """Create a topic."""
    fields, error = _topic_fields(request)
    if error:
        return JsonResponse({"error": error}, status=400)
    return JsonResponse(_topic_payload(topic_create(**fields)))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@manage_site_required
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
@manage_site_required
def topic_delete_view(request: HttpRequest, topic_id) -> JsonResponse:
    """Delete a topic."""
    try:
        topic = topic_get(topic_id=topic_id)
    except Topic.DoesNotExist:
        return JsonResponse({"error": _("Topic not found")}, status=404)
    topic_delete(topic=topic)
    return JsonResponse({"deleted": True, "id": str(topic_id)})


def _user_payload(user: User, *, viewer: User) -> dict:
    is_self = user.id == viewer.id
    can_manage = can_manage_app_users(viewer) and user_is_manageable(
        viewer=viewer, target=user
    )
    return {
        "id": user.id,
        "email": user.email,
        "name": user.get_full_name(),
        "joined": user.date_joined.strftime("%Y-%m-%d"),
        "is_active": user.is_active,
        "is_admin": getattr(user, "is_admin_member", False),
        "is_developer": getattr(user, "is_developer_member", False),
        "is_user_admin": getattr(user, "is_user_admin_member", False),
        "can_toggle_admin": (
            viewer.has_perm("app.manage_developers") or not is_self
        ),
        "can_toggle_developer": (
            viewer.has_perm("app.manage_developers") and not is_self
        ),
        # Resetting your own password is fine; locking yourself out isn't.
        "can_manage": can_manage,
        "can_lock_out": can_manage and not is_self,
    }


@require_GET
@ratelimit(key="ip", rate="120/m", method="GET", block=True)
def user_list_view(request: HttpRequest) -> JsonResponse:
    """Paginated users for the admin users tab; ``q`` filters by email.

    Site admins see every account; a user admin sees the app users only.
    """
    manages_site = request.user.has_perm("app.manage_site")
    if not manages_site and not can_manage_app_users(request.user):
        return JsonResponse({"error": _("Forbidden")}, status=403)
    search = (request.GET.get("q") or "").strip()
    paginator = Paginator(
        user_list(search=search, app_users_only=not manages_site),
        USERS_PER_PAGE,
    )
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
@manage_site_required
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
    return JsonResponse(
        {"id": target.id, "is_admin": user_admin_toggle(user=target)}
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@manage_developers_required
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


def _new_password(
    request: HttpRequest, *, user: User
) -> tuple[str | None, str | None]:
    """The confirmed new password from a create or reset, checked against
    the site's password rules. Returns ``(password, None)`` or
    ``(None, error_message)``."""
    password = request.POST.get("password") or ""
    if password != (request.POST.get("password_confirm") or ""):
        return None, _("The passwords don't match")
    try:
        validate_password(password, user=user)
    except ValidationError as e:
        return None, e.messages[0]
    return password, None


def _managed_user(
    request: HttpRequest, user_id: int
) -> tuple[User | None, JsonResponse | None]:
    """The account an app user action targets, or the error response when
    it doesn't exist or is outside what the viewer may manage."""
    try:
        target = user_get(user_id=user_id)
    except User.DoesNotExist:
        return None, JsonResponse({"error": _("User not found")}, status=404)
    if not user_is_manageable(viewer=request.user, target=target):
        return None, JsonResponse(
            {"error": _("You can't manage this account")}, status=403
        )
    return target, None


def _self_lockout(request: HttpRequest, target: User) -> JsonResponse | None:
    """Refuse an action that would lock the viewer out of their own access."""
    if target.id == request.user.id:
        return JsonResponse(
            {"error": _("You can't do that to your own account")}, status=403
        )
    return None


def _managed_user_payload(user: User, *, viewer: User) -> dict:
    """A single row, annotated the way the users list annotates them."""
    return _user_payload(user_list().get(pk=user.pk), viewer=viewer)


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@app_user_admin_required
def user_create_view(request: HttpRequest) -> JsonResponse:
    """Add an app user with the password an admin sets."""
    email = (request.POST.get("email") or "").strip()
    try:
        validate_email(email)
    except ValidationError:
        return JsonResponse(
            {"error": _("Enter a valid email address")}, status=400
        )
    if user_email_taken(email=email):
        return JsonResponse(
            {"error": _("Another account already uses that email")},
            status=400,
        )
    password, error = _new_password(request, user=User(email=email))
    if error:
        return JsonResponse({"error": error}, status=400)
    user = user_create(email=email, password=password)
    return JsonResponse(_managed_user_payload(user, viewer=request.user))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@app_user_admin_required
def user_password_view(request: HttpRequest, user_id: int) -> JsonResponse:
    """Set a new password for an account; the pilots send no reset email."""
    target, error_response = _managed_user(request, user_id)
    if error_response:
        return error_response
    password, error = _new_password(request, user=target)
    if error:
        return JsonResponse({"error": error}, status=400)
    user_password_set(user=target, password=password)
    return JsonResponse({"id": target.id})


def _active_set_view(request: HttpRequest, user_id: int, *, active: bool):
    target, error_response = _managed_user(request, user_id)
    if error_response:
        return error_response
    if lockout := _self_lockout(request, target):
        return lockout
    user_active_set(user=target, active=active)
    return JsonResponse(_managed_user_payload(target, viewer=request.user))


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@app_user_admin_required
def user_disable_view(request: HttpRequest, user_id: int) -> JsonResponse:
    """Disable an account: it can't log in, and everything it owns stays."""
    return _active_set_view(request, user_id, active=False)


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@app_user_admin_required
def user_enable_view(request: HttpRequest, user_id: int) -> JsonResponse:
    """Re-enable a disabled account."""
    return _active_set_view(request, user_id, active=True)


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@app_user_admin_required
def user_delete_view(request: HttpRequest, user_id: int) -> JsonResponse:
    """Delete an account and everything it owns. Permanent."""
    target, error_response = _managed_user(request, user_id)
    if error_response:
        return error_response
    if lockout := _self_lockout(request, target):
        return lockout
    user_delete(user=target)
    return JsonResponse({"id": user_id, "deleted": True})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@app_user_admin_required
def user_user_admin_toggle_view(
    request: HttpRequest, user_id: int
) -> JsonResponse:
    """Toggle a user's User admins membership."""
    target, error_response = _managed_user(request, user_id)
    if error_response:
        return error_response
    if lockout := _self_lockout(request, target):
        return lockout
    return JsonResponse(
        {"id": target.id, "is_user_admin": user_user_admin_toggle(user=target)}
    )
