from uuid import uuid4

from django.core.cache import cache

from litigant_portal.app.cache import bedrock_catalog_cache_key
from litigant_portal.app.selectors.bedrock import bedrock_policy


def bedrock_catalog_invalidate_on_error(error: Exception) -> None:
    """
    Request a bounded refresh after authorization or missing-model errors.
    """
    if getattr(error, "status_code", None) in {401, 403, 404}:
        key = bedrock_catalog_cache_key(bedrock_policy())
        cache.set(f"{key}:invalidated", uuid4().hex, timeout=3600)
