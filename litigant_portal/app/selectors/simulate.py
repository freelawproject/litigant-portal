from django.db.models import QuerySet

from litigant_portal.app.models import SimulatedUser


def simulated_user_list() -> QuerySet[SimulatedUser]:
    """All simulated users, oldest first, with identities attached."""
    return SimulatedUser.objects.select_related("identity")


def simulated_user_get(*, sim_id) -> SimulatedUser:
    """A single simulated user (raises SimulatedUser.DoesNotExist)."""
    return SimulatedUser.objects.select_related("identity").get(id=sim_id)
