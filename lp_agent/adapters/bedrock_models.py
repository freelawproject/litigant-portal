"""
Model classes and deployment policy, independent of Django and AWS clients.
"""

import re
from dataclasses import dataclass
from typing import Literal

from pydantic import AliasPath, AwareDatetime, BaseModel, Field


class BedrockModelUnavailable(RuntimeError):
    """
    No model satisfies the deployment's selection and routing requirements.
    """


@dataclass(frozen=True)
class ModelClass:
    label: str
    patterns: tuple[str, ...]
    native_api: Literal["converse", "openai"]
    mantle_api: Literal["chat", "responses"] | None
    vision: bool = False


# AWS catalogs do not identify model classes or all supported inference APIs.
# Keep that compatibility information here, without pinning release versions.
MODEL_CLASSES = {
    **{
        f"openai.{tier}": ModelClass(
            f"GPT {tier.title()}",
            (rf"openai\.gpt-(?P<version>\d+(?:\.\d+)*)-{tier}",),
            "openai",
            "responses",
            True,
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
        True,
    ),
    "zai.glm-flash": ModelClass(
        "GLM Flash",
        (r"zai\.glm-(?P<version>\d+(?:\.\d+)*)-flash",),
        "converse",
        "chat",
    ),
}

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
    enabled_classes: frozenset[str] = frozenset(MODEL_CLASSES)

    def __post_init__(self) -> None:
        if self.region not in GEOGRAPHY_REGIONS.get(self.geography, ()):
            raise BedrockModelUnavailable(
                "AWS_REGION must belong to BEDROCK_ALLOWED_GEOGRAPHY."
            )
        if (
            not self.enabled_classes
            or self.enabled_classes - MODEL_CLASSES.keys()
        ):
            raise BedrockModelUnavailable(
                "Invalid enabled Bedrock model classes."
            )

    def preference(self, model: str) -> tuple[str, str | None]:
        if not isinstance(model, str):
            raise BedrockModelUnavailable("Select an enabled Bedrock model.")
        if model.startswith("auto/"):
            selection = model.removeprefix("auto/"), None
        else:
            selection = model_class(model.removeprefix("bedrock_mantle/"))
        if selection is None or selection[0] not in self.enabled_classes:
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

    def invocation_options(self) -> dict[str, str]:
        options = {"model": self.model}
        if self.api_base:
            options["api_base"] = self.api_base
        if not self.model.startswith("openai/"):
            options["aws_region_name"] = self.region
        return options
