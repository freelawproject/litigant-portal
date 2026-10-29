"""
Model classes and deployment policy, independent of Django and AWS clients.
"""

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import AliasPath, AwareDatetime, BaseModel, Field

from lp_agent.errors import AgentError


class BedrockModelUnavailable(AgentError):
    """
    No model satisfies the deployment's selection and routing requirements.
    """


@dataclass(frozen=True)
class ModelClass:
    label: str
    patterns: tuple[str, ...]
    native_api: Literal["converse", "openai"] | None
    mantle_api: Literal["chat", "responses"] | None
    capabilities: frozenset[str] = frozenset()
    mantle_base: str = "v1"


# AWS catalogs do not identify model classes or all supported inference APIs.
# Keep that compatibility information here, without pinning release versions.
MODEL_CLASSES = {
    **{
        f"openai.{tier}": ModelClass(
            f"GPT {tier.title()}",
            (rf"openai\.gpt-(?P<version>\d+(?:\.\d+)*)-{tier}",),
            "openai",
            "responses",
            frozenset({"text", "stream", "tools", "image", "continuation"}),
            "openai/v1",
        )
        for tier in ("luna", "terra", "sol")
    },
    "anthropic.haiku": ModelClass(
        "Claude Haiku",
        (
            r"anthropic\.claude-haiku-(?P<version>\d+(?:-\d{1,2})?)(?:-\d{8})?(?:-v\d+:\d+)?",
            r"anthropic\.claude-(?P<version>\d+(?:-\d{1,2})?)-haiku(?:-\d{8})?(?:-v\d+:\d+)?",
        ),
        "converse",
        None,
        frozenset({"text", "stream", "tools", "image"}),
    ),
    "zai.glm-flash": ModelClass(
        "GLM Flash",
        (r"zai\.glm-(?P<version>\d+(?:\.\d+)*)-flash",),
        "converse",
        "chat",
        frozenset({"text", "stream", "tools"}),
    ),
}

ENABLED_MODEL_CLASSES = frozenset(MODEL_CLASSES)
MODEL_TIERS = {
    "tier/economy": ("Economy", "openai.luna"),
    "tier/balanced": ("Balanced", "openai.terra"),
    "tier/best": ("Best", "openai.sol"),
}
MODEL_CHOICES = tuple((key, label) for key, (label, _) in MODEL_TIERS.items())
PINNED_MODEL_CHOICES = {
    **{
        f"GPT_5_6_{tier.upper()}": (
            f"bedrock_mantle/openai.gpt-5.6-{tier}",
            f"GPT-5.6 {tier.title()}",
        )
        for tier in ("luna", "terra", "sol")
    },
    "CLAUDE_HAIKU_4_5": (
        "bedrock_mantle/anthropic.claude-haiku-4-5",
        "Claude Haiku 4.5",
    ),
    "GLM_4_7_FLASH": ("bedrock_mantle/zai.glm-4.7-flash", "GLM 4.7 Flash"),
}
MODEL_CHOICE_DEFINITIONS = {
    (
        "CLAUDE_HAIKU_AUTO"
        if class_id == "anthropic.haiku"
        else f"{class_id.replace('.', '_').replace('-', '_').upper()}_AUTO"
    ): (f"auto/{class_id}", f"{definition.label} (automatic)")
    for class_id, definition in MODEL_CLASSES.items()
}
MODEL_CHOICE_DEFINITIONS.update(PINNED_MODEL_CHOICES)
MODEL_CHOICE_DEFINITIONS.update(
    {
        key.removeprefix("tier/").upper(): (key, label)
        for key, label in MODEL_CHOICES
    }
)

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
    for class_id, definition in MODEL_CLASSES.items():
        for pattern in definition.patterns:
            if match := re.fullmatch(pattern, model_id):
                return class_id, match["version"].replace("-", ".")
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
        if (
            not ENABLED_MODEL_CLASSES
            or ENABLED_MODEL_CLASSES - MODEL_CLASSES.keys()
        ):
            raise BedrockModelUnavailable(
                "Invalid enabled Bedrock model classes."
            )

    def preference(self, model: str) -> tuple[str, str | None]:
        if not isinstance(model, str):
            raise BedrockModelUnavailable("Select an enabled Bedrock model.")
        if model in MODEL_TIERS:
            selection = MODEL_TIERS[model][1], None
        elif model.startswith("auto/"):
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
        if selection is None or selection[0] not in ENABLED_MODEL_CLASSES:
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
