from django.conf import settings
from django.core.cache import cache

from litigant_portal.agents import bedrock
from litigant_portal.agents.bedrock import (
    BedrockCatalog,
    BedrockModelUnavailable,
    BedrockPolicy,
    ResolvedBedrockModel,
)
from litigant_portal.app.cache import bedrock_catalog_cache_key


def bedrock_policy() -> BedrockPolicy:
    return BedrockPolicy(
        settings.AWS_REGION, settings.BEDROCK_ALLOWED_GEOGRAPHY
    )


def bedrock_catalog_get() -> BedrockCatalog:
    """
    Share discovery snapshots, including short-lived partial/error results.
    """
    policy = bedrock_policy()
    key = bedrock_catalog_cache_key(policy)
    catalog = cache.get(key)
    if catalog is None:
        try:
            catalog = bedrock.discover_catalog(
                policy, settings.BEDROCK_API_KEY
            )
        except BedrockModelUnavailable:
            # Cache safe text, never SDK exceptions with request credentials.
            catalog = "Bedrock discovery failed. Check model access and configuration."
        cache.set(
            key,
            catalog,
            timeout=3600
            if isinstance(catalog, BedrockCatalog) and catalog.complete
            else 300,
        )
    if isinstance(catalog, str):
        raise BedrockModelUnavailable(catalog)
    return catalog


def bedrock_model_target(
    *, model: str, required: frozenset[str] = frozenset({"text"})
) -> ResolvedBedrockModel:
    policy = bedrock_policy()
    policy.preference(model)
    return bedrock.resolve_catalog(
        bedrock_catalog_get(), policy, model, required
    )


def bedrock_model_list(
    *, required: frozenset[str] = frozenset({"text"})
) -> dict[str, ResolvedBedrockModel]:
    policy = bedrock_policy()
    catalog = bedrock_catalog_get()
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
    available = bedrock_model_list(required=bedrock.model_requirements(role))
    tiers = bedrock.model_tiers()
    choices = []
    for model, target in available.items():
        model_id = target.model.rsplit("/", 1)[-1].removeprefix("us.")
        _, version = bedrock.model_class(model_id)
        label = f"{bedrock.MODEL_MAPPING[model]} {version} ({tiers[model].capitalize()})"
        choices.append((model, label))
    return tuple(choices)
