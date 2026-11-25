from uuid import UUID

from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from litigant_portal.agents.assistant import LitigantAssistant
from litigant_portal.agents.tools.load_topic_flow import topic_flow_from_path
from litigant_portal.app.models import ChatThread, UserUpload
from litigant_portal.app.models.chat_engine import USER_CHAT_THREAD_TYPE
from litigant_portal.app.selectors.chat_engine import chat_thread_get
from litigant_portal.app.selectors.upload import user_upload_list
from litigant_portal.app.services.upload import (
    UploadValidationError,
    user_upload_create,
    user_upload_delete,
    user_upload_serialize,
)
from litigant_portal.app.views import chat_engine
from litigant_portal.app.views.utils import briefcase_answers, has_identity

# General chat endpoints


@require_POST
@ratelimit(key="ip", rate="20/m", method="POST", block=True)
def stream(request: HttpRequest):
    return chat_engine.stream(
        request,
        agent_class=LitigantAssistant,
        thread_type=USER_CHAT_THREAD_TYPE,
    )


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def thread_list(request: HttpRequest) -> JsonResponse:
    return chat_engine.thread_list(request, thread_type=USER_CHAT_THREAD_TYPE)


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def message_list(request: HttpRequest, thread_id) -> JsonResponse:
    return chat_engine.message_list(
        request,
        thread_id,
        agent_class=LitigantAssistant,
        thread_type=USER_CHAT_THREAD_TYPE,
    )


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def thread_usage(request: HttpRequest, thread_id) -> JsonResponse:
    if not request.user.is_superuser:
        return JsonResponse({"error": _("Forbidden")}, status=403)
    return chat_engine.thread_usage(
        request, thread_id, thread_type=USER_CHAT_THREAD_TYPE
    )


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def thread_delete(request: HttpRequest, thread_id) -> JsonResponse:
    return chat_engine.thread_delete(
        request, thread_id, thread_type=USER_CHAT_THREAD_TYPE
    )


# Assistant-specific endpoints


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def briefcase(request: HttpRequest) -> HttpResponse:
    """
    Refresh saved facts, scoped to the displayed thread's active flow.
    """
    flow = None
    if thread_id := request.GET.get("thread_id"):
        if not has_identity(request):
            raise Http404("Thread not found")
        try:
            thread = chat_thread_get(
                identity=request.identity,
                thread_id=UUID(thread_id),
                thread_type=USER_CHAT_THREAD_TYPE,
            )
        except (ValueError, ChatThread.DoesNotExist) as exc:
            raise Http404("Thread not found") from exc
        path = (thread.state or {}).get("active_topic_flow")
        flow = topic_flow_from_path(path) if path else None
    return render(
        request,
        "pages/chat/partials/_briefcase.html",
        {"briefcase_groups": briefcase_answers(request, flow=flow)},
    )


@require_GET
@ratelimit(key="ip", rate="60/m", method="GET", block=True)
def upload_list(request: HttpRequest) -> JsonResponse:
    """List the current identity's uploads for the attach-file picker."""
    uploads = [
        user_upload_serialize(upload)
        for upload in user_upload_list(identity=request.identity)
    ]
    return JsonResponse({"uploads": uploads})


@require_POST
@ratelimit(key="ip", rate="20/m", method="POST", block=True)
def upload_create(request: HttpRequest) -> JsonResponse:
    """Store a file uploaded from the attach-file picker."""
    file = request.FILES.get("file")
    if file is None:
        return JsonResponse({"error": _("No file uploaded")}, status=400)

    try:
        upload = user_upload_create(identity=request.identity, file=file)
    except UploadValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)

    return JsonResponse({"upload": user_upload_serialize(upload)})


@require_POST
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
def upload_delete(request: HttpRequest, upload_id) -> JsonResponse:
    """Permanently delete an upload owned by the current identity."""
    try:
        user_upload_delete(identity=request.identity, upload_id=upload_id)
    except UserUpload.DoesNotExist:
        return JsonResponse({"error": _("Upload not found")}, status=404)
    return JsonResponse({"deleted": True})
