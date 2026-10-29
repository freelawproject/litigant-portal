import hashlib
import logging
from contextlib import closing

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.cache import cache
from pydantic import ValidationError

from litigant_portal.app.models.choices import BedrockModel
from lp_agent.adapters.bedrock_discovery import (
    bedrock_client,
    discover_catalog,
    resolve_catalog,
)
from lp_agent.adapters.bedrock_models import (
    MODEL_CLASSES,
    BedrockModelUnavailable,
    BedrockPolicy,
    ResolvedBedrockModel,
)

logger = logging.getLogger(__name__)


def bedrock_policy() -> BedrockPolicy:
    return BedrockPolicy(
        settings.AWS_REGION,
        getattr(settings, "BEDROCK_ALLOWED_GEOGRAPHY", "US"),
        frozenset(
            getattr(settings, "BEDROCK_ENABLED_MODEL_CLASSES", MODEL_CLASSES)
        ),
    )


def bedrock_model_target(
    *,
    model: str,
    required: frozenset[str] = frozenset({"text"}),
) -> ResolvedBedrockModel:
    policy = bedrock_policy()
    policy.preference(model)
    fingerprint = hashlib.sha256(
        repr(
            (
                policy.region,
                policy.geography,
                sorted(policy.enabled_classes),
                settings.BEDROCK_API_KEY,
            )
        ).encode()
    ).hexdigest()
    catalog_key = f"bedrock:catalog:v2:{fingerprint}"
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


def bedrock_model_resolve(*, model: str) -> str:
    if model == BedrockModel.CLAUDE_HAIKU_AUTO:
        return bedrock_haiku_model()
    if model == BedrockModel.CLAUDE_HAIKU_4_5:
        return bedrock_haiku_model(version="4.5")
    return model


def bedrock_haiku_model(*, version: str | None = None) -> str:
    preference = (
        f"bedrock_mantle/anthropic.claude-haiku-{version.replace('.', '-')}"
        if version
        else BedrockModel.CLAUDE_HAIKU_AUTO
    )
    return bedrock_model_target(model=preference).model
