"""
Model classes and deployment policy, independent of Django and AWS clients.
"""

import re
from collections.abc import Collection
from dataclasses import dataclass
from typing import Literal

from pydantic import AliasPath, AwareDatetime, BaseModel, Field

from lp_agent.errors import AgentError


class BedrockModelUnavailable(AgentError):
    """
    No model satisfies the deployment's selection and routing requirements.
    """


@dataclass(frozen=True)
class ModelSeries:
    class_prefix: str
    patterns: tuple[str, ...]
    native_api: Literal["converse", "openai"] | None
    mantle_api: Literal["chat", "responses"] | None
    capabilities: frozenset[str] = frozenset()
    mantle_base: str = "v1"


MODEL_MAPPING: dict[str, str] = {
    "auto/openai.luna": "GPT Luna",
    "auto/openai.terra": "GPT Terra",
    "auto/openai.sol": "GPT Sol",
    "auto/anthropic.haiku": "Claude Haiku",
    "auto/zai.glm-flash": "GLM Flash",
}
MODEL_CHOICES: dict[str, list[str]] = {
    "economy": ["GPT Luna", "Claude Haiku"],
    "balanced": ["GPT Terra"],
    "best": ["GPT Sol"],
}

# Catalogs do not describe every inference API. These rules describe supported
# model series; deployment curation belongs only in the two mappings above.
MODEL_SERIES = (
    ModelSeries(
        "openai.",
        (r"openai\.gpt-(?P<version>\d+(?:\.\d+)*)-(?P<family>[a-z]+)",),
        "openai",
        "responses",
        frozenset({"text", "stream", "tools", "image", "continuation"}),
        "openai/v1",
    ),
    ModelSeries(
        "anthropic.",
        (
            r"anthropic\.claude-(?P<family>[a-z]+)-(?P<version>\d+(?:-\d{1,2})?)(?:-\d{8})?(?:-v\d+:\d+)?",
            r"anthropic\.claude-(?P<version>\d+(?:-\d{1,2})?)-(?P<family>[a-z]+)(?:-\d{8})?(?:-v\d+:\d+)?",
        ),
        "converse",
        None,
        frozenset({"text", "stream", "tools", "image"}),
    ),
    ModelSeries(
        "zai.glm",
        (r"zai\.glm-(?P<version>\d+(?:\.\d+)*)(?P<family>(?:-[a-z]+)*)",),
        "converse",
        "chat",
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
    Choose the first available model in the role's default tier.
    """
    tier = {"fast": "economy", "assistant": "balanced"}[role]
    for model, model_tier in model_tiers().items():
        if model_tier == tier and model in available:
            return model
    raise BedrockModelUnavailable(
        f"No available {tier} model for the {role} role."
    )


def model_series(class_id: str) -> ModelSeries:
    for definition in MODEL_SERIES:
        if class_id.startswith(definition.class_prefix):
            return definition
    raise BedrockModelUnavailable("Unsupported Bedrock model series.")


# These are geographic boundaries, not model availability tables. Unknown
# regions fail closed until their geography has been reviewed.
GEOGRAPHY_REGIONS = {
    "US": frozenset(
        [
            "us-east-1",
            "us-east-2",
            "us-west-1",
            "us-west-2",
            "us-gov-east-1",
            "us-gov-west-1",
        ]
    ),
    "CA": frozenset(["ca-central-1", "ca-west-1"]),
    "EU": frozenset(
        [
            "eu-central-1",
            "eu-central-2",
            "eu-west-1",
            "eu-west-2",
            "eu-west-3",
            "eu-north-1",
            "eu-south-1",
            "eu-south-2",
        ]
    ),
    "JP": frozenset(["ap-northeast-1", "ap-northeast-3"]),
    "AU": frozenset(["ap-southeast-2", "ap-southeast-4"]),
    "IN": frozenset(["ap-south-1", "ap-south-2"]),
    "APAC": frozenset(
        [
            "ap-east-2",
            "ap-northeast-1",
            "ap-northeast-2",
            "ap-northeast-3",
            "ap-south-1",
            "ap-south-2",
            "ap-southeast-1",
            "ap-southeast-2",
            "ap-southeast-3",
            "ap-southeast-4",
            "ap-southeast-5",
            "ap-southeast-6",
            "ap-southeast-7",
            "me-central-1",
        ]
    ),
}


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
        if self.region not in GEOGRAPHY_REGIONS.get(self.geography, ()):
            raise BedrockModelUnavailable(
                "AWS_REGION must belong to BEDROCK_ALLOWED_GEOGRAPHY."
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
            prefix, _, unprefixed = model_id.partition(".")
            if prefix.upper() in GEOGRAPHY_REGIONS:
                model_id = unprefixed
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


@dataclass(frozen=True)
class ResolvedBedrockModel:
    model: str
    region: str
    api_base: str | None = None
    native_responses: bool = False
    capabilities: frozenset[str] = frozenset()
    billing_model: str | None = None

    def invocation_options(self) -> dict[str, str]:
        options = {"model": self.model}
        if self.api_base:
            options["api_base"] = self.api_base
        if not self.model.startswith("openai/"):
            options["aws_region_name"] = self.region
        return options

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
            model=self.billing_model or self.model,
            region_name=self.region,
        )
