"""
Bedrock catalog discovery and model selection, independent of Django.
"""

import logging
import re
from collections.abc import Collection
from contextlib import closing
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import (
    AliasPath,
    AwareDatetime,
    BaseModel,
    Field,
    ValidationError,
)

logger = logging.getLogger(__name__)


class BedrockModelUnavailable(Exception):
    """
    No model satisfies the deployment's selection and routing requirements.
    """


class BedrockDiscoveryError(BedrockModelUnavailable):
    """
    Expose a diagnostic code without retaining a provider response or message.
    """

    def __init__(self, code: str) -> None:
        self.code = (
            code
            if isinstance(code, str)
            and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", code)
            else "UnknownError"
        )
        super().__init__(
            f"Bedrock discovery failed ({self.code}). Check model access and configuration."
        )


@dataclass(frozen=True)
class ModelSeries:
    class_prefix: str
    patterns: tuple[str, ...]
    native_capabilities: frozenset[str]
    mantle_capabilities: frozenset[str] = frozenset()
    mantle_base: str = "v1"
    small_task_effort: str | None = None
    regional_pricing_alias: str | None = None


MODEL_MAPPING: dict[str, str] = {
    "auto/openai.luna": "GPT Luna",
    "auto/openai.terra": "GPT Terra",
    "auto/openai.sol": "GPT Sol",
    "auto/anthropic.haiku": "Claude Haiku",
    "auto/zai.glm-flash": "GLM Flash",
}
MODEL_CHOICES: dict[str, list[str]] = {
    "economy": ["GPT Luna", "Claude Haiku", "GLM Flash"],
    "balanced": ["GPT Terra"],
    "best": ["GPT Sol"],
}

# Catalogs do not describe every inference API. These rules describe supported
# model series; deployment curation belongs only in the two mappings above.
MODEL_SERIES = (
    ModelSeries(
        "openai.",
        (r"openai\.gpt-(?P<version>\d+(?:\.\d+)*)-(?P<family>[a-z]+)",),
        frozenset({"text", "stream", "tools", "image"}),
        # Mantle chat completions cannot preserve function tools with reasoning.
        frozenset({"text", "stream", "image"}),
        "openai/v1",
        small_task_effort="low",
        regional_pricing_alias="us.",
    ),
    ModelSeries(
        "anthropic.",
        (
            r"anthropic\.claude-(?P<family>[a-z]+)-(?P<version>\d+(?:-\d{1,2})?)(?:-\d{8})?(?:-v\d+:\d+)?",
            r"anthropic\.claude-(?P<version>\d+(?:-\d{1,2})?)-(?P<family>[a-z]+)(?:-\d{8})?(?:-v\d+:\d+)?",
        ),
        frozenset({"text", "stream", "tools", "image", "document"}),
    ),
    ModelSeries(
        "zai.glm",
        (r"zai\.glm-(?P<version>\d+(?:\.\d+)*)(?P<family>(?:-[a-z]+)*)",),
        frozenset({"text", "stream", "tools"}),
        frozenset({"text", "stream", "tools"}),
    ),
)


def model_tiers() -> dict[str, str]:
    """
    Validate curation and index enabled model identifiers in display order.
    """
    by_label = {label: model for model, label in MODEL_MAPPING.items()}
    if len(by_label) != len(MODEL_MAPPING) or any(
        not model.startswith("auto/") or not label
        for model, label in MODEL_MAPPING.items()
    ):
        raise BedrockModelUnavailable(
            "Invalid MODEL_MAPPING identifiers or labels."
        )
    if MODEL_CHOICES.keys() != {"economy", "balanced", "best"}:
        raise BedrockModelUnavailable(
            "MODEL_CHOICES must define economy, balanced, and best."
        )
    tiers = {}
    for tier in ("economy", "balanced", "best"):
        for label in MODEL_CHOICES[tier]:
            model = by_label.get(label)
            if model is None or model in tiers:
                raise BedrockModelUnavailable(
                    "MODEL_CHOICES contains an unknown or duplicate model."
                )
            model_series(model.removeprefix("auto/"))
            tiers[model] = tier
    return tiers


def model_choices() -> tuple[tuple[str, str], ...]:
    """
    Static choices for validation, without AWS access during model loading.
    """
    return tuple(
        (model, f"{MODEL_MAPPING[model]} ({tier})")
        for model, tier in model_tiers().items()
    )


def default_model(role: str, available: Collection[str]) -> str:
    """
    Prefer the role's default tier, allowing only cheaper-tier fallbacks.
    """
    tiers = {"fast": ("economy",), "assistant": ("balanced", "economy")}[role]
    enabled = model_tiers()
    for tier in tiers:
        for model, model_tier in enabled.items():
            if model_tier == tier and model in available:
                return model
    raise BedrockModelUnavailable(
        f"No available model in the allowed tiers for the {role} role."
    )


def model_requirements(role: str) -> frozenset[str]:
    """
    Require streaming and function tools for the portal's main assistant.
    """
    return frozenset(
        {"text", "stream", "tools"} if role == "assistant" else {"text"}
    )


def model_series(class_id: str) -> ModelSeries:
    for definition in MODEL_SERIES:
        if class_id.startswith(definition.class_prefix):
            return definition
    raise BedrockModelUnavailable("Unsupported Bedrock model series.")


# Unknown regions fail closed until their US routing has been reviewed.
US_REGIONS = frozenset(
    {
        "us-east-1",
        "us-east-2",
        "us-west-1",
        "us-west-2",
        "us-gov-east-1",
        "us-gov-west-1",
    }
)


def model_class(model_id: str) -> tuple[str, str] | None:
    """
    Associate native and Mantle identifiers only through known class patterns.
    """
    for definition in MODEL_SERIES:
        for pattern in definition.patterns:
            if match := re.fullmatch(pattern, model_id):
                return (
                    f"{definition.class_prefix}{match['family']}",
                    match["version"].replace("-", "."),
                )
    return None


@dataclass(frozen=True)
class BedrockPolicy:
    region: str
    geography: str = "US"

    def __post_init__(self) -> None:
        if self.geography != "US":
            raise BedrockModelUnavailable(
                "Only US Bedrock routing is supported."
            )
        if self.region not in US_REGIONS:
            raise BedrockModelUnavailable(
                "AWS_REGION must be a reviewed US region."
            )
        model_tiers()

    def preference(self, model: str) -> tuple[str, str | None]:
        if not isinstance(model, str):
            raise BedrockModelUnavailable("Select an enabled Bedrock model.")
        if model.startswith("auto/"):
            selection = model.removeprefix("auto/"), None
        else:
            model_id = (
                model.removeprefix(f"bedrock/converse/{self.region}/")
                .removeprefix(f"bedrock_mantle/{self.region}/")
                .removeprefix("bedrock_mantle/")
                .removeprefix("openai/")
            )
            model_id = model_id.removeprefix("us.")
            selection = model_class(model_id)
        if selection is None or f"auto/{selection[0]}" not in model_tiers():
            raise BedrockModelUnavailable(
                "The selected model class is not enabled."
            )
        return selection


class FoundationModel(BaseModel):
    model_id: str = Field(alias="modelId")
    input_modalities: frozenset[str] = Field(
        default_factory=frozenset, alias="inputModalities"
    )
    output_modalities: frozenset[str] = Field(
        default_factory=frozenset, alias="outputModalities"
    )
    inference_types: frozenset[str] = Field(
        default_factory=frozenset, alias="inferenceTypesSupported"
    )
    streaming: bool = Field(False, alias="responseStreamingSupported")
    status: str = Field(
        "", validation_alias=AliasPath("modelLifecycle", "status")
    )
    released: AwareDatetime | None = Field(
        None, validation_alias=AliasPath("modelLifecycle", "startOfLifeTime")
    )


class MantleModel(BaseModel):
    id: str
    created: AwareDatetime
    status: str = "available"


class ProfileModel(BaseModel):
    arn: str = Field(alias="modelArn")


class InferenceProfile(BaseModel):
    id: str = Field(alias="inferenceProfileId")
    status: str
    type: str
    models: tuple[ProfileModel, ...]


@dataclass(frozen=True)
class BedrockCatalog:
    native: tuple[FoundationModel, ...]
    mantle: tuple[MantleModel, ...]
    profiles: tuple[InferenceProfile, ...]
    complete: bool = True
    authorized_model_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ResolvedBedrockModel:
    model: str
    region: str
    api_base: str | None = None
    capabilities: frozenset[str] = frozenset()
    billing_model: str | None = None
    small_task_effort: str | None = None

    def invocation_options(
        self, *, small_task: bool = False
    ) -> dict[str, str]:
        options = {"model": self.model}
        if self.api_base:
            options["api_base"] = self.api_base
        options["aws_region_name"] = self.region
        if small_task and self.small_task_effort:
            options["reasoning_effort"] = self.small_task_effort
        return options

    def pricing_model(self) -> str:
        """
        Resolve a pricing identity without changing the invocation route.
        """
        from litellm import model_cost

        billing_model = self.billing_model or self.model
        regional = (
            f"bedrock_mantle/{self.region}/{billing_model.removeprefix('bedrock_mantle/')}"
            if billing_model.startswith("bedrock_mantle/")
            else f"bedrock/{self.region}/{billing_model}"
        )
        identity = model_class(billing_model)
        if regional in model_cost:
            billing_model = regional
        elif (
            billing_model not in model_cost
            and identity is not None
            and self.region in US_REGIONS
            and not self.region.startswith("us-gov-")
            and (alias := model_series(identity[0]).regional_pricing_alias)
            and (alias_model := f"{alias}{billing_model}") in model_cost
        ):
            # Commercial GPT in-region and US geographic rates match for
            # the same release. This changes pricing identity, never routing.
            billing_model = alias_model

        return billing_model

    def completion_cost(self, usage: BaseModel | dict) -> float:
        """
        Price the resolved Bedrock route, independent of transport metadata.
        """
        from litellm import completion_cost

        return completion_cost(
            completion_response={
                "usage": usage.model_dump()
                if isinstance(usage, BaseModel)
                else usage,
            },
            model=self.pricing_model(),
            region_name=self.region,
        )


def _bedrock_client(policy: BedrockPolicy, api_key: str) -> Any:
    """
    Use the caller's token without reading or changing global credentials.
    """
    import boto3
    from botocore.config import Config
    from botocore.session import Session
    from botocore.tokens import ScopedEnvTokenProvider, TokenProviderChain

    if not api_key.strip():
        raise BedrockDiscoveryError("MissingApiKey")
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


def discover_catalog(policy: BedrockPolicy, api_key: str) -> BedrockCatalog:
    """
    Load account metadata and access once, without inference or Django state.
    """
    from openai import APIError, OpenAI

    try:
        with closing(_bedrock_client(policy, api_key)) as client:
            native = tuple(
                FoundationModel.model_validate(model)
                for model in client.list_foundation_models()["modelSummaries"]
            )
            profiles = tuple(
                InferenceProfile.model_validate(profile)
                for page in client.get_paginator(
                    "list_inference_profiles"
                ).paginate(typeEquals="SYSTEM_DEFINED")
                for profile in page["inferenceProfileSummaries"]
            )
            complete = True
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
                logger.warning(
                    "Mantle catalog unavailable (%s, status=%s)",
                    type(error).__name__,
                    getattr(error, "status_code", None),
                )
                models, complete = (), False
            catalog = BedrockCatalog(
                native, models, profiles, complete=complete
            )
            enabled = {model.removeprefix("auto/") for model in model_tiers()}
            authorized = set()
            for model in native:
                identity = model_class(model.model_id)
                if (
                    identity is None
                    or identity[0] not in enabled
                    or not _native_routes(model, catalog, policy)
                ):
                    continue
                availability = client.get_foundation_model_availability(
                    modelId=model.model_id
                )
                if (
                    availability.get("authorizationStatus") == "AUTHORIZED"
                    and availability.get("entitlementAvailability")
                    == "AVAILABLE"
                    and availability.get("regionAvailability") == "AVAILABLE"
                    and availability.get("agreementAvailability", {}).get(
                        "status"
                    )
                    == "AVAILABLE"
                ):
                    authorized.add(model.model_id)
            return BedrockCatalog(
                native,
                models,
                profiles,
                complete=complete,
                authorized_model_ids=frozenset(authorized),
            )
    except ClientError as error:
        raise BedrockDiscoveryError(
            error.response.get("Error", {}).get("Code", "ClientError")
        ) from None
    except (BotoCoreError, ValidationError) as error:
        raise BedrockDiscoveryError(type(error).__name__) from None


def _native_routes(
    model: FoundationModel, catalog: BedrockCatalog, policy: BedrockPolicy
) -> list[tuple[int, str]]:
    if (
        model.status != "ACTIVE"
        or model.released is None
        or "TEXT" not in model.input_modalities & model.output_modalities
    ):
        return []
    if "ON_DEMAND" in model.inference_types:
        return [(0, model.model_id)]
    routes = []
    partition = "aws-us-gov" if policy.region.startswith("us-gov-") else "aws"
    for profile in catalog.profiles:
        if (
            profile.status != "ACTIVE"
            or profile.type != "SYSTEM_DEFINED"
            or not profile.id.startswith("us.")
            or not profile.models
        ):
            continue
        destinations = [item.arn.split(":", 5) for item in profile.models]
        if all(
            len(arn) == 6
            and arn[:3] == ["arn", partition, "bedrock"]
            and arn[3] in US_REGIONS
            and arn[4] == ""
            and arn[5] == f"foundation-model/{model.model_id}"
            for arn in destinations
        ):
            routes.append((2, profile.id))
    return routes


def resolve_catalog(
    catalog: BedrockCatalog,
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
            or model.model_id not in catalog.authorized_model_ids
            or model.released is None
        ):
            continue
        capabilities = set(definition.native_capabilities)
        if not model.streaming:
            capabilities.discard("stream")
        if "IMAGE" not in model.input_modalities:
            capabilities.discard("image")
        if not required <= capabilities:
            continue
        routes = _native_routes(model, catalog, policy)
        if not routes:
            continue
        for priority, invocation_id in routes:
            target = ResolvedBedrockModel(
                model=f"bedrock/converse/{policy.region}/{invocation_id}",
                region=policy.region,
                capabilities=frozenset(capabilities),
                billing_model=invocation_id,
                small_task_effort=definition.small_task_effort,
            )
            candidates.append((model.released, identity, priority, target))
    for model in catalog.mantle:
        identity = model_class(model.id)
        if (
            identity is None
            or identity[0] != class_id
            or (pinned is not None and identity[1] != pinned)
            or model.status != "available"
            or not definition.mantle_capabilities
        ):
            continue
        dates = release_dates.get(identity, {model.created})
        if len(dates) != 1:
            raise BedrockModelUnavailable("Ambiguous model release metadata.")
        capabilities = definition.mantle_capabilities
        if required <= capabilities:
            target = ResolvedBedrockModel(
                f"bedrock_mantle/{policy.region}/{model.id}",
                policy.region,
                f"https://bedrock-mantle.{policy.region}.api.aws/{definition.mantle_base}",
                frozenset(capabilities),
                f"bedrock_mantle/{model.id}",
                small_task_effort=definition.small_task_effort,
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
