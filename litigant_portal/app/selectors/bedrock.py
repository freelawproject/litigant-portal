import logging
import time
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

from litigant_portal.agents import bedrock
from litigant_portal.agents.bedrock import (
    BedrockCatalog,
    BedrockDiscoveryError,
    BedrockModelUnavailable,
    BedrockPolicy,
    ResolvedBedrockModel,
)
from litigant_portal.app.cache import bedrock_catalog_cache_key

logger = logging.getLogger(__name__)
_REFRESH_SECONDS = 60


@dataclass(frozen=True)
class _CatalogEntry:
    value: BedrockCatalog | str
    invalidation: str | None
    refresh_after: float


def bedrock_policy() -> BedrockPolicy:
    return BedrockPolicy(
        settings.AWS_REGION, settings.BEDROCK_ALLOWED_GEOGRAPHY
    )


def bedrock_catalog_get() -> BedrockCatalog:
    """
    Share fresh discovery results and limit refresh starts across workers.
    """
    policy = bedrock_policy()
    key = bedrock_catalog_cache_key(policy)
    entry: _CatalogEntry | None = cache.get(key)
    invalidation = cache.get(f"{key}:invalidated")
    refresh = entry is None or (
        isinstance(entry.value, BedrockCatalog)
        and (
            time.time() >= entry.refresh_after
            or (
                invalidation is not None and entry.invalidation != invalidation
            )
        )
    )
    if refresh:
        # Let the guard expire naturally; deleting it could release another
        # worker's claim after a slow discovery outlives this interval.
        if cache.add(f"{key}:refresh", True, timeout=_REFRESH_SECONDS):
            value: BedrockCatalog | str
            try:
                value = bedrock.discover_catalog(
                    policy, settings.BEDROCK_API_KEY
                )
                timeout = 3600 if value.complete else 300
                refresh_after = time.time() + (3300 if value.complete else 240)
            except BedrockDiscoveryError as error:
                value, timeout = error.code, _REFRESH_SECONDS
                refresh_after = time.time() + _REFRESH_SECONDS
                logger.warning("Bedrock discovery failed (%s)", error.code)
            entry = _CatalogEntry(value, invalidation, refresh_after)
            cache.set(key, entry, timeout=timeout)
        else:
            entry = cache.get(key)
    if entry is None:
        raise BedrockModelUnavailable(
            "Bedrock discovery is in progress. Please try again shortly."
        )
    if isinstance(entry.value, str):
        raise BedrockDiscoveryError(entry.value)
    return entry.value


def bedrock_model_target(
    *, model: str, required: frozenset[str] = frozenset({"text"})
) -> ResolvedBedrockModel:
    policy = bedrock_policy()
    policy.preference(model)
    return bedrock.resolve_catalog(
        bedrock_catalog_get(), policy, model, required
    )


def bedrock_model_list(
    *,
    required: frozenset[str] = frozenset({"text"}),
    catalog: BedrockCatalog | None = None,
) -> dict[str, ResolvedBedrockModel]:
    policy = bedrock_policy()
    if catalog is None:
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
    *, role: str = "fast", catalog: BedrockCatalog | None = None
) -> tuple[tuple[str, str], ...]:
    available = bedrock_model_list(
        required=bedrock.model_requirements(role), catalog=catalog
    )
    tiers = bedrock.model_tiers()
    choices = []
    for model, target in available.items():
        model_id = target.model.rsplit("/", 1)[-1].removeprefix("us.")
        _, version = bedrock.model_class(model_id)
        label = f"{bedrock.MODEL_MAPPING[model]} {version} ({tiers[model].capitalize()})"
        choices.append((model, label))
    return tuple(choices)
