from django.conf import settings
from django.core.cache import cache

from litigant_portal.agents.bedrock import BedrockPolicy
from litigant_portal.app.cache import bedrock_catalog_cache_key


def bedrock_catalog_invalidate_on_error(error: Exception) -> None:
    """
    Refresh external access metadata after authorization or missing-model errors.
    """
    if getattr(error, "status_code", None) in {401, 403, 404}:
        policy = BedrockPolicy(
            settings.AWS_REGION, settings.BEDROCK_ALLOWED_GEOGRAPHY
        )
        cache.delete(bedrock_catalog_cache_key(policy))
