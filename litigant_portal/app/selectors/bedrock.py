import hashlib
import json
from dataclasses import asdict

from django.conf import settings
from django.core.cache import cache

from litigant_portal.agents import bedrock
from litigant_portal.agents.bedrock import (
    BedrockCatalog,
    BedrockModelUnavailable,
    BedrockPolicy,
    ResolvedBedrockModel,
)


def bedrock_policy() -> BedrockPolicy:
    return BedrockPolicy(
        settings.AWS_REGION, settings.BEDROCK_ALLOWED_GEOGRAPHY
    )


def _cache_key(policy: BedrockPolicy) -> str:
    fingerprint = hashlib.sha256(
        json.dumps(
            (
                policy.region,
                policy.geography,
                bedrock.MODEL_MAPPING,
                bedrock.MODEL_CHOICES,
                [asdict(definition) for definition in bedrock.MODEL_SERIES],
                settings.BEDROCK_API_KEY,
            ),
            sort_keys=True,
            default=sorted,
        ).encode()
    ).hexdigest()
    return f"bedrock:catalog:v1:{fingerprint}"


def _catalog(policy: BedrockPolicy) -> BedrockCatalog:
    key = _cache_key(policy)
    catalog = cache.get(key)
    if catalog is None:
        catalog = bedrock.discover_catalog(policy, settings.BEDROCK_API_KEY)
        if catalog.complete:
            cache.set(key, catalog, timeout=3600)
    return catalog


def bedrock_model_failed(error: Exception) -> None:
    """
    Invalidate account metadata without retrying the failed inference.
    """
    if getattr(error, "status_code", None) in {400, 401, 403, 404}:
        cache.delete(_cache_key(bedrock_policy()))


def bedrock_model_target(
    *, model: str, required: frozenset[str] = frozenset({"text"})
) -> ResolvedBedrockModel:
    policy = bedrock_policy()
    policy.preference(model)
    return bedrock.resolve_catalog(_catalog(policy), policy, model, required)


def bedrock_available_models(
    *, required: frozenset[str] = frozenset({"text"})
) -> dict[str, ResolvedBedrockModel]:
    policy = bedrock_policy()
    catalog = _catalog(policy)
    available = {}
    for model in bedrock.model_tiers():
        try:
            available[model] = bedrock.resolve_catalog(
                catalog, policy, model, required
            )
        except BedrockModelUnavailable:
            continue
    return available


def bedrock_model_choices(
    *, role: str = "fast"
) -> tuple[tuple[str, str], ...]:
    available = bedrock_available_models(
        required=bedrock.model_requirements(role)
    )
    return tuple(
        (model, label)
        for model, label in bedrock.model_choices()
        if model in available
    )
