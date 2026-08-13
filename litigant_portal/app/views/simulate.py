"""Admin simulate panel API: simulated users, their documents, and runs.

Every endpoint is admin-gated. The stream/thread endpoints delegate to the
generic chat engine views with the simulated user's identity swapped in,
so both sides of a simulation run through the exact machinery a real
conversation uses.
"""

import json

from django.http import HttpRequest, JsonResponse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from litigant_portal.agents import LitigantAssistant, SimulatedLitigant
from litigant_portal.app.models import (
    ChatThread,
    SimulatedUser,
    TopicFlow,
    UserUpload,
)
from litigant_portal.app.selectors.chat_engine import chat_thread_list
from litigant_portal.app.selectors.simulate import (
    simulated_user_get,
    simulated_user_list,
)
from litigant_portal.app.selectors.site import site_get_model
from litigant_portal.app.selectors.topic_flow import topic_flow_get_public
from litigant_portal.app.selectors.upload import user_upload_list
from litigant_portal.app.services.simulate import (
    SIMULATION_ACTOR_THREAD_TYPE,
    SIMULATION_THREAD_TYPE,
    simulated_user_create,
    simulated_user_delete,
    simulated_user_serialize,
    simulated_user_update,
    simulation_run_create,
    simulation_run_serialize,
)
from litigant_portal.app.services.upload import (
    UploadValidationError,
    user_upload_create,
    user_upload_delete,
    user_upload_serialize,
)
from litigant_portal.app.views import chat_engine
from litigant_portal.app.views.topic_flow import topic_flow_summary_payload
from litigant_portal.app.views.utils import manage_site_required


def _sim_or_none(sim_id) -> SimulatedUser | None:
    try:
        return simulated_user_get(sim_id=sim_id)
    except SimulatedUser.DoesNotExist:
        return None


def _not_found() -> JsonResponse:
    return JsonResponse({"error": _("Simulated user not found")}, status=404)


def _json_body(request: HttpRequest) -> dict:
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


# --- Simulated users ------------------------------------------------------


@require_GET
@manage_site_required
def simulated_user_list_view(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "simulated_users": [
                simulated_user_serialize(sim) for sim in simulated_user_list()
            ]
        }
    )


@require_POST
@manage_site_required
def simulated_user_create_view(request: HttpRequest) -> JsonResponse:
    data = _json_body(request)
    name = str(data.get("name") or "").strip() or str(_("New user"))
    story = str(data.get("story") or "")
    sim = simulated_user_create(name=name, story=story)
    return JsonResponse({"simulated_user": simulated_user_serialize(sim)})


@require_POST
@manage_site_required
def simulated_user_update_view(request: HttpRequest, sim_id) -> JsonResponse:
    sim = _sim_or_none(sim_id)
    if sim is None:
        return _not_found()
    data = _json_body(request)
    name = data.get("name")
    if name is not None:
        name = str(name).strip()
        if not name:
            return JsonResponse({"error": _("Name is required")}, status=400)
    story = data.get("story")
    sim = simulated_user_update(
        sim=sim,
        name=name,
        story=None if story is None else str(story),
    )
    return JsonResponse({"simulated_user": simulated_user_serialize(sim)})


@require_POST
@manage_site_required
def simulated_user_delete_view(request: HttpRequest, sim_id) -> JsonResponse:
    sim = _sim_or_none(sim_id)
    if sim is None:
        return _not_found()
    simulated_user_delete(sim=sim)
    return JsonResponse({"deleted": True})


# --- Documents (the simulated user's upload bank) -------------------------


@require_GET
@manage_site_required
def simulated_upload_list_view(request: HttpRequest, sim_id) -> JsonResponse:
    sim = _sim_or_none(sim_id)
    if sim is None:
        return _not_found()
    return JsonResponse(
        {
            "uploads": [
                user_upload_serialize(upload)
                for upload in user_upload_list(identity=sim.identity)
            ]
        }
    )


@require_POST
@manage_site_required
def simulated_upload_create_view(request: HttpRequest, sim_id) -> JsonResponse:
    sim = _sim_or_none(sim_id)
    if sim is None:
        return _not_found()
    file = request.FILES.get("file")
    if file is None:
        return JsonResponse({"error": _("No file uploaded")}, status=400)
    try:
        upload = user_upload_create(identity=sim.identity, file=file)
    except UploadValidationError as e:
        return JsonResponse({"error": str(e)}, status=400)
    return JsonResponse({"upload": user_upload_serialize(upload)})


@require_POST
@manage_site_required
def simulated_upload_delete_view(
    request: HttpRequest, sim_id, upload_id
) -> JsonResponse:
    sim = _sim_or_none(sim_id)
    if sim is None:
        return _not_found()
    try:
        user_upload_delete(identity=sim.identity, upload_id=upload_id)
    except UserUpload.DoesNotExist:
        return JsonResponse({"error": _("Upload not found")}, status=404)
    return JsonResponse({"deleted": True})


# --- Runs -----------------------------------------------------------------


@require_GET
@manage_site_required
def simulation_run_list_view(request: HttpRequest, sim_id) -> JsonResponse:
    sim = _sim_or_none(sim_id)
    if sim is None:
        return _not_found()
    return JsonResponse(
        {
            "runs": [
                simulation_run_serialize(thread)
                for thread in chat_thread_list(
                    identity=sim.identity,
                    thread_type=SIMULATION_THREAD_TYPE,
                )
            ]
        }
    )


@require_POST
@manage_site_required
def simulation_run_create_view(request: HttpRequest, sim_id) -> JsonResponse:
    sim = _sim_or_none(sim_id)
    if sim is None:
        return _not_found()
    return JsonResponse({"run": simulation_run_create(sim=sim)})


@require_GET
@manage_site_required
def simulation_thread_view(request: HttpRequest, sim_id, thread_id):
    """The assistant-side thread, rendered for the simulate panel."""
    sim = _sim_or_none(sim_id)
    if sim is None:
        return _not_found()
    return chat_engine.message_list(
        request,
        thread_id,
        agent_class=LitigantAssistant,
        thread_type=SIMULATION_THREAD_TYPE,
        identity=sim.identity,
    )


@require_POST
@manage_site_required
def simulation_thread_delete_view(
    request: HttpRequest, sim_id, thread_id
) -> JsonResponse:
    """Delete a run: the assistant-side thread and its actor peer."""
    sim = _sim_or_none(sim_id)
    if sim is None:
        return _not_found()
    try:
        thread = ChatThread.objects.get(
            id=thread_id,
            identity=sim.identity,
            thread_type=SIMULATION_THREAD_TYPE,
        )
    except ChatThread.DoesNotExist:
        return JsonResponse({"error": _("Thread not found")}, status=404)
    actor_id = (thread.state or {}).get("actor_thread_id")
    if actor_id:
        ChatThread.objects.filter(
            id=actor_id,
            identity=sim.identity,
            thread_type=SIMULATION_ACTOR_THREAD_TYPE,
        ).delete()
    thread.delete()
    return JsonResponse({"deleted": True})


@require_GET
@manage_site_required
def simulation_topic_flow_summary_view(
    request: HttpRequest, sim_id, topic_slug, flow_slug
) -> JsonResponse:
    """A flow's briefcase-card summary computed for the simulated user's
    identity (the public summary endpoint would report the admin's own
    answers instead)."""
    sim = _sim_or_none(sim_id)
    if sim is None:
        return _not_found()
    try:
        flow = topic_flow_get_public(
            topic_slug=topic_slug, flow_slug=flow_slug
        )
    except TopicFlow.DoesNotExist:
        return JsonResponse({"error": _("Flow not found")}, status=404)
    return JsonResponse(
        topic_flow_summary_payload(flow=flow, identity=sim.identity)
    )


# --- Streams --------------------------------------------------------------


@require_POST
@manage_site_required
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
def simulation_assistant_stream_view(request: HttpRequest, sim_id):
    """One assistant turn on the simulated user's conversation."""
    sim = _sim_or_none(sim_id)
    if sim is None:
        return _not_found()
    return chat_engine.stream(
        request,
        agent_class=LitigantAssistant,
        thread_type=SIMULATION_THREAD_TYPE,
        model=site_get_model(role="assistant"),
        identity=sim.identity,
    )


@require_POST
@manage_site_required
@ratelimit(key="ip", rate="60/m", method="POST", block=True)
def simulation_actor_stream_view(request: HttpRequest, sim_id):
    """One simulated-user turn: the actor decides what the person says."""
    sim = _sim_or_none(sim_id)
    if sim is None:
        return _not_found()
    return chat_engine.stream(
        request,
        agent_class=SimulatedLitigant,
        thread_type=SIMULATION_ACTOR_THREAD_TYPE,
        model=site_get_model(role="assistant"),
        identity=sim.identity,
    )
