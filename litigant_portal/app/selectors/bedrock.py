import hashlib
import json
import logging
from contextlib import closing
from dataclasses import asdict
from typing import Any
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.cache import cache
from pydantic import ValidationError

from litigant_portal.agents import bedrock as bedrock_models
from litigant_portal.agents.bedrock import (
    GEOGRAPHY_REGIONS,
    BedrockCatalog,
    BedrockModelUnavailable,
    BedrockPolicy,
    FoundationModel,
    InferenceProfile,
    MantleModel,
    ResolvedBedrockModel,
    model_class,
    model_series,
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


def bedrock_model_choices(
    *, role: str = "fast"
) -> tuple[tuple[str, str], ...]:
    available = bedrock_available_models(
        required=bedrock_models.model_requirements(role)
    )
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
            for model in keys:
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
                logger.info("Resolved Bedrock model: %s", target.model)
            if catalog.complete:
                cache.set(catalog_key, catalog, timeout=3600)
                cache.set_many(
                    {
                        keys[model]: target
                        for model, target in resolved.items()
                    },
                    timeout=3600,
                )
    except (BotoCoreError, ClientError, ValidationError) as error:
        raise BedrockModelUnavailable(
            f"Bedrock discovery failed ({type(error).__name__}). Check model access and configuration."
        ) from None
    return resolved


def bedrock_client(policy: BedrockPolicy, api_key: str) -> Any:
    """
    Use the caller's token without reading or changing global credentials.
    """
    import boto3
    from botocore.config import Config
    from botocore.session import Session
    from botocore.tokens import ScopedEnvTokenProvider, TokenProviderChain

    if not api_key.strip():
        raise BedrockModelUnavailable("A Bedrock API key is required.")
    session = Session()
    session.register_component(
        "token_provider",
        TokenProviderChain(
            [
                ScopedEnvTokenProvider(
                    session, {"AWS_BEARER_TOKEN_BEDROCK": api_key}
                )
            ]
        ),
    )
    return boto3.Session(botocore_session=session).client(
        "bedrock",
        region_name=policy.region,
        config=Config(
            signature_version="bearer",
            connect_timeout=3,
            read_timeout=5,
            retries={"mode": "standard", "total_max_attempts": 2},
        ),
    )


def discover_catalog(
    client: Any, policy: BedrockPolicy, api_key: str
) -> BedrockCatalog:
    """
    Read both catalogs; an unavailable Mantle endpoint cannot authorize a route.
    """
    from openai import APIError, OpenAI

    native = tuple(
        FoundationModel.model_validate(model)
        for model in client.list_foundation_models()["modelSummaries"]
    )
    profiles = tuple(
        InferenceProfile.model_validate(profile)
        for page in client.get_paginator("list_inference_profiles").paginate(
            typeEquals="SYSTEM_DEFINED"
        )
        for profile in page["inferenceProfileSummaries"]
    )
    try:
        with OpenAI(
            api_key=api_key,
            base_url=f"https://bedrock-mantle.{policy.region}.api.aws/v1",
            timeout=5,
            max_retries=1,
        ) as mantle:
            models = tuple(
                MantleModel.model_validate(model.model_dump())
                for model in mantle.models.list()
            )
    except APIError as error:
        logger.warning("Mantle catalog unavailable (%s)", type(error).__name__)
        return BedrockCatalog(native, (), profiles, complete=False)
    return BedrockCatalog(native, models, profiles)


def _native_routes(
    model: FoundationModel, catalog: BedrockCatalog, policy: BedrockPolicy
) -> list[tuple[int, str]]:
    if "ON_DEMAND" in model.inference_types:
        return [(0, model.model_id)]
    routes = []
    partition = "aws-us-gov" if policy.region.startswith("us-gov-") else "aws"
    for profile in catalog.profiles:
        if (
            profile.status != "ACTIVE"
            or profile.type != "SYSTEM_DEFINED"
            or profile.id.partition(".")[0].upper() not in GEOGRAPHY_REGIONS
            or not profile.models
        ):
            continue
        destinations = [item.arn.split(":", 5) for item in profile.models]
        if all(
            len(arn) == 6
            and arn[:3] == ["arn", partition, "bedrock"]
            and arn[3] in GEOGRAPHY_REGIONS[policy.geography]
            and arn[4] == ""
            and arn[5] == f"foundation-model/{model.model_id}"
            for arn in destinations
        ):
            routes.append((2, profile.id))
    return routes


def resolve_catalog(
    catalog: BedrockCatalog,
    client: Any,
    policy: BedrockPolicy,
    preference: str,
    required: frozenset[str] = frozenset({"text"}),
) -> ResolvedBedrockModel:
    """
    Select newest eligible version first, then prefer regional inference.
    """
    class_id, pinned = policy.preference(preference)
    definition = model_series(class_id)
    candidates = []
    release_dates = {}
    for model in catalog.native:
        identity = model_class(model.model_id)
        if identity is None or identity[0] != class_id:
            continue
        if model.released is not None:
            release_dates.setdefault(identity, set()).add(model.released)
        if (
            (pinned is not None and identity[1] != pinned)
            or model.status != "ACTIVE"
            or definition.native_api is None
            or model.released is None
            or "TEXT" not in model.input_modalities & model.output_modalities
        ):
            continue
        capabilities = set(definition.capabilities)
        if not model.streaming:
            capabilities.discard("stream")
        if "IMAGE" not in model.input_modalities:
            capabilities.discard("image")
        if not required <= capabilities:
            continue
        routes = _native_routes(model, catalog, policy)
        if not routes:
            continue
        if model.model_id not in catalog.availability:
            availability = client.get_foundation_model_availability(
                modelId=model.model_id
            )
            catalog.availability[model.model_id] = (
                availability.get("authorizationStatus") == "AUTHORIZED"
                and availability.get("entitlementAvailability") == "AVAILABLE"
                and availability.get("regionAvailability") == "AVAILABLE"
                and availability.get("agreementAvailability", {}).get("status")
                == "AVAILABLE"
            )
        if not catalog.availability[model.model_id]:
            logger.info("Bedrock model unavailable: %s", model.model_id)
            continue
        for priority, invocation_id in routes:
            target = ResolvedBedrockModel(
                model=f"bedrock/converse/{policy.region}/{invocation_id}",
                region=policy.region,
                capabilities=frozenset(capabilities),
                billing_model=invocation_id,
            )
            candidates.append((model.released, identity, priority, target))
    for model in catalog.mantle:
        identity = model_class(model.id)
        if (
            identity is None
            or identity[0] != class_id
            or (pinned is not None and identity[1] != pinned)
            or model.status != "available"
            or definition.mantle_api is None
        ):
            continue
        dates = release_dates.get(identity, {model.created})
        if len(dates) != 1:
            raise BedrockModelUnavailable("Ambiguous model release metadata.")
        capabilities = set(definition.capabilities)
        if class_id.startswith("openai."):
            # Mantle chat completions cannot preserve the assistant's tool
            # behavior with reasoning enabled. Use Converse for those calls.
            capabilities.discard("tools")
        if required <= capabilities:
            target = ResolvedBedrockModel(
                f"bedrock_mantle/{policy.region}/{model.id}",
                policy.region,
                f"https://bedrock-mantle.{policy.region}.api.aws/{definition.mantle_base}",
                frozenset(capabilities),
                f"bedrock_mantle/{model.id}",
            )
            candidates.append((next(iter(dates)), identity, 1, target))
    if not candidates:
        raise BedrockModelUnavailable(
            "No eligible model is available for the selected class and geography."
        )
    newest = max(candidate[0] for candidate in candidates)
    latest = [candidate for candidate in candidates if candidate[0] == newest]
    if len({candidate[1] for candidate in latest}) != 1:
        raise BedrockModelUnavailable(
            "Cannot distinguish the newest model version."
        )
    return min(
        latest, key=lambda candidate: (candidate[2], candidate[3].model)
    )[3]
