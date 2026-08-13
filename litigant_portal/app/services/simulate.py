"""Simulated user lifecycle and simulation runs.

A simulation run is a *pair* of chat threads sharing the simulated user's
identity: the assistant-side thread (``simulation``) where the litigant
assistant operates exactly as it would for a real person, and the
actor-side thread (``simulation_actor``) where the simulator agent decides
what the "user" says next. Each thread's state carries its peer's id so a
run can be resumed later; the pairing is written before either agent runs,
and both agents' state models allow extra keys, so it survives their own
state writes.
"""

from django.db import transaction

from litigant_portal.app.models import ChatThread, SimulatedUser, UserIdentity
from litigant_portal.app.selectors.upload import user_upload_list

SIMULATION_THREAD_TYPE = "simulation"
SIMULATION_ACTOR_THREAD_TYPE = "simulation_actor"


def simulated_user_create(*, name: str, story: str = "") -> SimulatedUser:
    """Create a simulated user with its own backing identity."""
    with transaction.atomic():
        identity = UserIdentity.objects.create()
        return SimulatedUser.objects.create(
            identity=identity, name=name, story=story
        )


def simulated_user_update(
    *, sim: SimulatedUser, name: str | None = None, story: str | None = None
) -> SimulatedUser:
    """Update a simulated user's persona fields."""
    if name is not None:
        sim.name = name
    if story is not None:
        sim.story = story
    sim.save(update_fields=["name", "story", "updated_at"])
    return sim


def simulated_user_delete(*, sim: SimulatedUser) -> None:
    """Delete a simulated user and everything it owns.

    Deletes the backing identity: the cascade removes the simulated user
    row plus its threads, uploads, and topic flow answers in one go. The
    cascade never touches storage, so the upload files are dropped
    explicitly first (the codebase's pattern for every file-bearing row).
    """
    for upload in user_upload_list(identity=sim.identity):
        upload.file.delete(save=False)
    sim.identity.delete()


def simulated_user_serialize(sim: SimulatedUser) -> dict:
    """JSON shape for the admin simulate panel."""
    return {
        "id": str(sim.id),
        "name": sim.name,
        "story": sim.story,
        "created_at": sim.created_at.isoformat(),
    }


def simulation_run_create(*, sim: SimulatedUser) -> dict:
    """Create a linked pair of threads for one simulation run."""
    with transaction.atomic():
        assistant_thread = ChatThread.objects.create(
            identity=sim.identity, thread_type=SIMULATION_THREAD_TYPE
        )
        actor_thread = ChatThread.objects.create(
            identity=sim.identity,
            thread_type=SIMULATION_ACTOR_THREAD_TYPE,
            state={"assistant_thread_id": str(assistant_thread.id)},
        )
        assistant_thread.state = {"actor_thread_id": str(actor_thread.id)}
        assistant_thread.save(update_fields=["state", "updated_at"])
    return {
        "assistant_thread_id": str(assistant_thread.id),
        "actor_thread_id": str(actor_thread.id),
    }


def simulation_run_serialize(thread: ChatThread) -> dict:
    """JSON shape for one run (an assistant-side thread) in the run picker."""
    return {
        "assistant_thread_id": str(thread.id),
        "actor_thread_id": (thread.state or {}).get("actor_thread_id"),
        "description": thread.description,
        "updated_at": thread.updated_at.isoformat(),
    }
