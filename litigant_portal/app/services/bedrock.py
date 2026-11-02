from django.core.cache import cache

from litigant_portal.app.cache import bedrock_catalog_cache_key
from litigant_portal.app.selectors.bedrock import bedrock_policy


def bedrock_catalog_invalidate_on_error(error: Exception) -> None:
    """
    Refresh external access metadata after authorization or missing-model errors.
    """
    if getattr(error, "status_code", None) in {401, 403, 404}:
        cache.delete(bedrock_catalog_cache_key(bedrock_policy()))
