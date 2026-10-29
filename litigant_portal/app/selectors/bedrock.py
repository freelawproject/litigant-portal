import hashlib
import json
import logging
from contextlib import closing
from dataclasses import asdict
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.cache import cache
from pydantic import ValidationError

from lp_agent.adapters.bedrock_discovery import (
    bedrock_client,
    discover_catalog,
    resolve_catalog,
)
from lp_agent.adapters.bedrock_models import (
    ENABLED_MODEL_CLASSES,
    MODEL_CLASSES,
    MODEL_TIERS,
    BedrockModelUnavailable,
    BedrockPolicy,
    ResolvedBedrockModel,
)

logger = logging.getLogger(__name__)


def bedrock_policy() -> BedrockPolicy:
    return BedrockPolicy(
        settings.AWS_REGION,
        settings.BEDROCK_ALLOWED_GEOGRAPHY,
    )


def _cache_scope(policy: BedrockPolicy) -> str:
    fingerprint = hashlib.sha256(
        json.dumps(
            (
                policy.region,
                policy.geography,
                sorted(ENABLED_MODEL_CLASSES),
                MODEL_TIERS,
                {
                    name: asdict(definition)
                    for name, definition in MODEL_CLASSES.items()
                },
                settings.BEDROCK_API_KEY,
            ),
            sort_keys=True,
            default=sorted,
        ).encode()
    ).hexdigest()
    return f"bedrock:v3:{fingerprint}"


def bedrock_model_failed(error: Exception) -> None:
    """
    Refresh account metadata after access or model-route failures, without retrying inference.
    """
    if getattr(error, "status_code", None) in {400, 401, 403, 404}:
        cache.delete(_cache_scope(bedrock_policy()))


def bedrock_model_target(
    *,
    model: str,
    required: frozenset[str] = frozenset({"text"}),
) -> ResolvedBedrockModel:
    policy = bedrock_policy()
    policy.preference(model)
    scope = _cache_scope(policy)
    generation = cache.get_or_set(scope, lambda: uuid4().hex, timeout=3600)
    catalog_key = f"{scope}:{generation}"
    resolution_key = f"{catalog_key}:{model}:{','.join(sorted(required))}"
    if resolved := cache.get(resolution_key):
        return resolved
    try:
        with closing(
            bedrock_client(policy, settings.BEDROCK_API_KEY)
        ) as client:
            catalog = cache.get(catalog_key)
            if catalog is None:
                catalog = discover_catalog(
                    client, policy, settings.BEDROCK_API_KEY
                )
                if catalog.complete:
                    cache.set(catalog_key, catalog, timeout=3600)
            resolved = resolve_catalog(
                catalog, client, policy, model, required
            )
    except (BotoCoreError, ClientError, ValidationError) as error:
        raise BedrockModelUnavailable(
            f"Bedrock discovery failed ({type(error).__name__}). Check model access and configuration."
        ) from None
    if catalog.complete:
        cache.set(resolution_key, resolved, timeout=3600)
    logger.info("Resolved Bedrock model: %s", resolved.model)
    return resolved
