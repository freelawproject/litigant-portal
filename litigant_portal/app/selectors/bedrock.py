import hashlib
import logging
from contextlib import closing
from datetime import datetime
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.cache import cache

from litigant_portal.app.models.choices import BedrockModel

logger = logging.getLogger(__name__)


class BedrockModelUnavailable(RuntimeError):
    """
    A model preference cannot be resolved for this deployment.
    """


def bedrock_model_resolve(*, model: str) -> str:
    """
    Resolve Haiku preferences while preserving other LiteLLM model strings.
    """
    if model == BedrockModel.CLAUDE_HAIKU_AUTO:
        return bedrock_haiku_model()
    if model == BedrockModel.CLAUDE_HAIKU_4_5:
        return bedrock_haiku_model(version="4.5")
    return model


def _invocation_id(
    model: dict[str, Any], profiles: list[dict[str, Any]], region: str
) -> str | None:
    """
    Prefer regional inference, then an unambiguous geographic profile.
    """
    model_id = model["modelId"]
    if "ON_DEMAND" in model.get("inferenceTypesSupported", []):
        return model_id

    matches = []
    for profile in profiles:
        profile_id = profile["inferenceProfileId"]
        if (
            profile.get("status") != "ACTIVE"
            or profile.get("type") != "SYSTEM_DEFINED"
            or profile_id.startswith("global.")
        ):
            continue
        destinations = [
            item["modelArn"].split(":", 5)
            for item in profile.get("models", [])
        ]
        # Inspect every destination, not just the profile's name. Unknown
        # destinations and routes outside the source geography are ineligible.
        if destinations and all(
            len(arn) == 6
            and arn[3].split("-")[0] == region.split("-")[0]
            and arn[5] == f"foundation-model/{model_id}"
            for arn in destinations
        ):
            matches.append(profile_id)
    if len(matches) > 1:
        raise BedrockModelUnavailable(
            "Multiple geographic Haiku profiles match this deployment."
        )
    return matches[0] if matches else None


def _discover_haiku(*, region: str, version: str | None) -> str:
    with closing(
        boto3.client(
            "bedrock",
            region_name=region,
            config=Config(
                connect_timeout=3,
                read_timeout=5,
                retries={"mode": "standard", "total_max_attempts": 2},
            ),
        )
    ) as client:
        models = client.list_foundation_models(
            byProvider="Anthropic", byOutputModality="TEXT"
        )["modelSummaries"]
        profiles = [
            profile
            for page in client.get_paginator(
                "list_inference_profiles"
            ).paginate(typeEquals="SYSTEM_DEFINED")
            for profile in page["inferenceProfileSummaries"]
        ]
        candidates: list[tuple[datetime, str]] = []
        for model in models:
            if (
                model.get("providerName") != "Anthropic"
                or "haiku" not in model.get("modelName", "").casefold()
                or model.get("modelLifecycle", {}).get("status") != "ACTIVE"
                or "TEXT" not in model.get("inputModalities", [])
                or "TEXT" not in model.get("outputModalities", [])
                or (
                    version is not None
                    and model["modelName"] != f"Claude Haiku {version}"
                )
            ):
                continue
            availability = client.get_foundation_model_availability(
                modelId=model["modelId"]
            )
            if (
                availability.get("authorizationStatus") != "AUTHORIZED"
                or availability.get("entitlementAvailability") != "AVAILABLE"
                or availability.get("regionAvailability") != "AVAILABLE"
                or availability.get("agreementAvailability", {}).get("status")
                != "AVAILABLE"
            ):
                continue
            invocation_id = _invocation_id(model, profiles, region)
            if invocation_id is None:
                continue
            launched = model["modelLifecycle"].get("startOfLifeTime")
            if (
                not isinstance(launched, datetime)
                or launched.utcoffset() is None
            ):
                raise BedrockModelUnavailable(
                    "Haiku discovery returned no usable launch timestamp."
                )
            candidates.append((launched, invocation_id))

    if not candidates:
        raise BedrockModelUnavailable(
            "No eligible Haiku model is available in the configured geography. "
            "Check model access and agreements in AWS Bedrock."
        )
    candidates.sort(reverse=True)
    if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
        raise BedrockModelUnavailable(
            "Haiku discovery cannot distinguish the newest model."
        )
    return f"bedrock/converse/{region}/{candidates[0][1]}"


def bedrock_haiku_model(*, version: str | None = None) -> str:
    """
    Resolve Haiku with this deployment's credentials and cache for one hour.
    """
    region = settings.AWS_REGION
    api_key = settings.BEDROCK_API_KEY
    if not region or not api_key:
        raise BedrockModelUnavailable(
            "Haiku discovery requires AWS_REGION and AWS_BEARER_TOKEN_BEDROCK."
        )
    fingerprint = hashlib.sha256(
        f"{region}\0{api_key}\0{version or 'automatic'}".encode()
    ).hexdigest()
    cache_key = f"bedrock:haiku:v1:{fingerprint}"
    resolved = cache.get(cache_key)
    if resolved is None:
        try:
            resolved = _discover_haiku(region=region, version=version)
        except (BotoCoreError, ClientError) as error:
            raise BedrockModelUnavailable(
                f"Bedrock Haiku discovery failed ({type(error).__name__}). "
                "Check the deployment's region, credentials, and discovery "
                "permissions."
            ) from None
        cache.set(cache_key, resolved, timeout=3600)
        logger.info("Resolved Haiku model: %s", resolved)
    return resolved
