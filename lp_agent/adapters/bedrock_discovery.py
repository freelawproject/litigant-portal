"""
Discover account-visible models and select a compatible geographic route.
"""

import logging
from contextlib import closing
from typing import Any

from lp_agent.adapters.bedrock_models import (
    GEOGRAPHY_REGIONS,
    MODEL_CLASSES,
    BedrockCatalog,
    BedrockModelUnavailable,
    BedrockPolicy,
    FoundationModel,
    InferenceProfile,
    MantleModel,
    ResolvedBedrockModel,
    model_class,
)

logger = logging.getLogger(__name__)


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
    definition = MODEL_CLASSES[class_id]
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
        if definition.native_api != "openai":
            capabilities.discard("continuation")
        if not required <= capabilities:
            continue
        routes = _native_routes(model, catalog, policy)
        if not routes:
            continue
        availability = client.get_foundation_model_availability(
            modelId=model.model_id
        )
        if (
            availability.get("authorizationStatus") != "AUTHORIZED"
            or availability.get("entitlementAvailability") != "AVAILABLE"
            or availability.get("regionAvailability") != "AVAILABLE"
            or availability.get("agreementAvailability", {}).get("status")
            != "AVAILABLE"
        ):
            logger.info("Bedrock model unavailable: %s", model.model_id)
            continue
        for priority, invocation_id in routes:
            native_responses = definition.native_api == "openai"
            target = ResolvedBedrockModel(
                model=(
                    f"openai/{invocation_id}"
                    if native_responses
                    else f"bedrock/converse/{policy.region}/{invocation_id}"
                ),
                region=policy.region,
                api_base=(
                    f"https://bedrock-runtime.{policy.region}.amazonaws.com/openai/v1"
                    if native_responses
                    else None
                ),
                native_responses=native_responses,
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
        native_responses = definition.mantle_api == "responses"
        if not native_responses:
            capabilities.discard("continuation")
        if required <= capabilities:
            target = ResolvedBedrockModel(
                (
                    f"openai/{model.id}"
                    if native_responses
                    else f"bedrock_mantle/{policy.region}/{model.id}"
                ),
                policy.region,
                f"https://bedrock-mantle.{policy.region}.api.aws/{definition.mantle_base}",
                native_responses,
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


def resolve_models(
    *,
    policy: BedrockPolicy,
    api_key: str,
    preferences: tuple[str, ...],
    required: frozenset[str] = frozenset({"text"}),
) -> dict[str, ResolvedBedrockModel]:
    """
    Share one discovery snapshot across standalone model and judge selections.
    """
    from botocore.exceptions import BotoCoreError, ClientError
    from pydantic import ValidationError

    for preference in preferences:
        policy.preference(preference)
    try:
        with closing(bedrock_client(policy, api_key)) as client:
            catalog = discover_catalog(client, policy, api_key)
            return {
                preference: resolve_catalog(
                    catalog, client, policy, preference, required
                )
                for preference in dict.fromkeys(preferences)
            }
    except (BotoCoreError, ClientError, ValidationError) as error:
        raise BedrockModelUnavailable(
            f"Bedrock discovery failed ({type(error).__name__}). Check model access and configuration."
        ) from None
