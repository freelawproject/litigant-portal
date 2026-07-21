from django.http import HttpRequest, JsonResponse
from django.views.decorators.http import require_GET

from litigant_portal.app.services.health import (
    check_database,
    check_redis,
    check_storage,
)


@require_GET
def health(request: HttpRequest) -> JsonResponse:
    """Health check for services."""
    services = {
        "database": check_database(),
        "redis": check_redis(),
        "storage_private": check_storage("default"),
        "storage_public": check_storage("public"),
    }
    healthy = all(services.values())
    return JsonResponse(
        {
            "status": healthy,
            "services": services,
        },
        status=200 if healthy else 503,
    )
