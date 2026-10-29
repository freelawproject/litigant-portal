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

from lp_agent.adapters import bedrock_models
from lp_agent.adapters.bedrock_discovery import (
    bedrock_client,
    discover_catalog,
    resolve_catalog,
)
from lp_agent.adapters.bedrock_models import (
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
                bedrock_models.MODEL_MAPPING,
                bedrock_models.MODEL_CHOICES,
                [
                    asdict(definition)
                    for definition in bedrock_models.MODEL_SERIES
                ],
                settings.BEDROCK_API_KEY,
            ),
            sort_keys=True,
            default=sorted,
        ).encode()
    ).hexdigest()
    return f"bedrock:v4:{fingerprint}"


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
    return _model_targets((model,), required=required)[model]


def bedrock_available_models(
    *,
    required: frozenset[str] = frozenset({"text"}),
) -> dict[str, ResolvedBedrockModel]:
    """
    Resolve enabled choices together against one cached discovery snapshot.
    """
    return _model_targets(
        tuple(bedrock_models.model_tiers()),
        required=required,
        available_only=True,
    )


def bedrock_model_choices() -> tuple[tuple[str, str], ...]:
    available = bedrock_available_models()
    return tuple(
        (model, label)
        for model, label in bedrock_models.model_choices()
        if model in available
    )


def _model_targets(
    models: tuple[str, ...],
    *,
    required: frozenset[str],
    available_only: bool = False,
) -> dict[str, ResolvedBedrockModel]:
    policy = bedrock_policy()
    for model in models:
        policy.preference(model)
    scope = _cache_scope(policy)
    generation = cache.get_or_set(scope, lambda: uuid4().hex, timeout=3600)
    catalog_key = f"{scope}:{generation}"
    keys = {
        model: f"{catalog_key}:{model}:{','.join(sorted(required))}"
        for model in models
    }
    resolved = {
        model: target
        for model, key in keys.items()
        if (target := cache.get(key)) is not None
    }
    if len(resolved) == len(keys):
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
            for model, key in keys.items():
                if model in resolved:
                    continue
                try:
                    target = resolve_catalog(
                        catalog, client, policy, model, required
                    )
                except BedrockModelUnavailable:
                    if not available_only:
                        raise
                    continue
                resolved[model] = target
                if catalog.complete:
                    cache.set(key, target, timeout=3600)
                logger.info("Resolved Bedrock model: %s", target.model)
    except (BotoCoreError, ClientError, ValidationError) as error:
        raise BedrockModelUnavailable(
            f"Bedrock discovery failed ({type(error).__name__}). Check model access and configuration."
        ) from None
    return resolved
