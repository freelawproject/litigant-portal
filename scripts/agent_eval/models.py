"""
Resolve evaluation selections through the application's Bedrock catalog.
"""

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from litigant_portal.agents import bedrock

if TYPE_CHECKING:
    from .schema import Config


def resolve_models(config: "Config") -> dict:
    policy = bedrock.BedrockPolicy(
        os.environ.get("AWS_REGION", "us-east-1"),
        os.environ.get("BEDROCK_ALLOWED_GEOGRAPHY", "US"),
    )
    catalog = bedrock.discover_catalog(
        policy, os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")
    )
    application = any(system != "raw" for system in config.systems)
    required = (
        bedrock.model_requirements("assistant")
        if application
        else frozenset({"text", "stream"})
    )
    candidates = {
        model: bedrock.resolve_catalog(
            catalog, policy, model, required
        ).invocation_options()
        for model in config.models
    }
    judges = {
        model: bedrock.resolve_catalog(
            catalog, policy, model, bedrock.model_requirements("judge")
        ).invocation_options(small_task=True)
        for model in config.judges
        if "current" in config.systems
    }
    fast = None
    if application:
        preference = config.legacy_fast_model
        if preference is None:
            available = {}
            for model in bedrock.model_tiers():
                try:
                    available[model] = bedrock.resolve_catalog(
                        catalog,
                        policy,
                        model,
                        bedrock.model_requirements("fast"),
                    )
                except bedrock.BedrockModelUnavailable:
                    continue
            fast = available[bedrock.default_model("fast", available)]
        else:
            fast = bedrock.resolve_catalog(
                catalog,
                policy,
                preference,
                bedrock.model_requirements("fast"),
            )
    return {
        "discovered_at": datetime.now(UTC).isoformat(),
        "models": candidates,
        "judges": judges,
        "fast": fast.invocation_options(small_task=True) if fast else None,
    }


def pinned_evaluator_options(model: str) -> dict[str, str]:
    """
    Keep the evaluator's explicit version, region, and Mantle route fixed.
    """
    parts = model.split("/")
    if len(parts) != 3 or parts[0] != "bedrock_mantle":
        raise ValueError(
            "evaluator_model must be bedrock_mantle/REGION/MODEL_ID."
        )
    _, region, model_id = parts
    identity = bedrock.model_class(model_id)
    if region not in bedrock.US_REGIONS or identity is None:
        raise ValueError(
            "Select a versioned Mantle evaluator in a reviewed US region."
        )
    definition = bedrock.model_series(identity[0])
    if not definition.mantle_capabilities:
        raise ValueError("Select a versioned Mantle evaluator model.")
    return bedrock.ResolvedBedrockModel(
        model=model,
        region=region,
        api_base=(
            f"https://bedrock-mantle.{region}.api.aws/{definition.mantle_base}"
        ),
        billing_model=f"bedrock_mantle/{model_id}",
    ).invocation_options()


def evaluator_options(model: str) -> dict[str, str]:
    # Old artifacts retain their original unqualified provider identifiers.
    if model.startswith("bedrock_mantle/") and model.count("/") == 2:
        return pinned_evaluator_options(model)
    return {"model": model}
