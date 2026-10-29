from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from django.core.cache import cache
from django.test import RequestFactory

from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.models import ChatThread, Site
from litigant_portal.app.models.choices import BedrockModel
from litigant_portal.app.selectors.bedrock import (
    BedrockModelUnavailable,
    bedrock_model_failed,
    bedrock_model_target,
)
from litigant_portal.app.services.chat_engine import (
    chat_thread_generate_description,
)
from litigant_portal.app.views.assistant import stream

OLD_MODEL = "anthropic.claude-haiku-4-5-20251001-v1:0"
NEW_MODEL = "anthropic.claude-haiku-5-5"


@pytest.fixture
def discovery(settings):
    settings.AWS_REGION = "us-east-1"
    settings.BEDROCK_ALLOWED_GEOGRAPHY = "US"
    settings.BEDROCK_API_KEY = "test-bedrock-key"
    client = Mock(
        spec=[
            "list_foundation_models",
            "get_paginator",
            "get_foundation_model_availability",
            "close",
        ]
    )
    models = [
        {
            "modelId": model_id,
            "modelName": f"Claude Haiku {version}",
            "providerName": "Anthropic",
            "inputModalities": ["TEXT"],
            "outputModalities": ["TEXT"],
            "responseStreamingSupported": True,
            "inferenceTypesSupported": ["INFERENCE_PROFILE"],
            "modelLifecycle": {
                "status": "ACTIVE",
                "startOfLifeTime": datetime(year, 10, 1, tzinfo=UTC),
            },
        }
        for model_id, version, year in (
            (OLD_MODEL, "4.5", 2025),
            (NEW_MODEL, "5.5", 2026),
        )
    ]
    profiles = [
        {
            "inferenceProfileId": f"us.{model['modelId']}",
            "type": "SYSTEM_DEFINED",
            "status": "ACTIVE",
            "models": [
                {
                    "modelArn": (
                        "arn:aws:bedrock:us-east-1::foundation-model/"
                        f"{model['modelId']}"
                    )
                }
            ],
        }
        for model in models
    ]
    client.list_foundation_models.return_value = {"modelSummaries": models}
    client.get_paginator.return_value.paginate.return_value = [
        {"inferenceProfileSummaries": profiles}
    ]
    client.get_foundation_model_availability.return_value = {
        "authorizationStatus": "AUTHORIZED",
        "entitlementAvailability": "AVAILABLE",
        "regionAvailability": "AVAILABLE",
        "agreementAvailability": {"status": "AVAILABLE"},
    }
    with (
        patch(
            "litigant_portal.app.selectors.bedrock.bedrock_client",
            return_value=client,
        ) as create_client,
        patch("openai.OpenAI") as mantle,
    ):
        mantle.return_value.__enter__.return_value.models.list.return_value = []
        yield SimpleNamespace(
            client=client,
            models=models,
            profiles=profiles,
            create_client=create_client,
            mantle=mantle.return_value.__enter__.return_value,
        )


@pytest.mark.parametrize(
    ("preference", "model_id"),
    [("", NEW_MODEL), (BedrockModel.CLAUDE_HAIKU_4_5, OLD_MODEL)],
)
def test_description_uses_discovered_model_and_books_usage(
    discovery, preference, model_id
):
    cache.set(SITE_CACHE_KEY, Site(fast_model=preference))
    thread = ChatThread()
    thread.save = Mock()
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=" Name Change Help ")
            )
        ],
        usage=SimpleNamespace(total_tokens=16),
    )
    with (
        patch(
            "litigant_portal.app.services.chat_engine.chat_message_list",
            return_value=[
                SimpleNamespace(data={"role": "user", "content": "Help"})
            ],
        ),
        patch("litellm.completion", return_value=response) as completion,
        patch("litellm.completion_cost", return_value=0.001),
        patch(
            "litigant_portal.app.services.chat_engine.chat_message_inject_meta"
        ) as inject_meta,
    ):
        assert (
            chat_thread_generate_description(thread=thread)
            == "Name Change Help"
        )
    resolved = f"bedrock/converse/us-east-1/us.{model_id}"
    assert completion.call_args.kwargs["model"] == resolved
    assert thread.description == "Name Change Help"
    thread.save.assert_called_once_with(
        update_fields=["description", "updated_at"]
    )
    inject_meta.assert_called_once_with(
        thread_id=thread.id,
        kind="thread_description",
        model=resolved,
        num_tokens=16,
        cost=0.001,
    )


@pytest.mark.parametrize(
    "scenario", ["agreement", "global", "other_geography", "eu", "regional"]
)
def test_discovery_respects_access_and_geography(
    discovery, settings, scenario
):
    region, prefix, expected = "us-east-1", "us.", NEW_MODEL
    if scenario == "agreement":
        available = (
            discovery.client.get_foundation_model_availability.return_value
        )
        discovery.client.get_foundation_model_availability.side_effect = (
            lambda *, modelId: {
                **available,
                "agreementAvailability": {
                    "status": "NOT_AVAILABLE"
                    if modelId == NEW_MODEL
                    else "AVAILABLE"
                },
            }
        )
        expected = OLD_MODEL
    elif scenario == "global":
        discovery.profiles[1]["inferenceProfileId"] = f"global.{NEW_MODEL}"
        expected = OLD_MODEL
    elif scenario == "other_geography":
        discovery.profiles[1]["models"].append(
            {
                "modelArn": f"arn:aws:bedrock:eu-west-1::foundation-model/{NEW_MODEL}"
            }
        )
        expected = OLD_MODEL
    elif scenario == "eu":
        settings.AWS_REGION = region = "eu-west-1"
        settings.BEDROCK_ALLOWED_GEOGRAPHY = "EU"
        prefix = "eu."
        for profile in discovery.profiles:
            profile["inferenceProfileId"] = profile[
                "inferenceProfileId"
            ].replace("us.", "eu.")
            for model in profile["models"]:
                model["modelArn"] = model["modelArn"].replace(
                    "us-east-1", region
                )
    else:
        discovery.models[1]["inferenceTypesSupported"] = ["ON_DEMAND"]
        prefix = ""
    assert (
        bedrock_model_target(model=BedrockModel.CLAUDE_HAIKU_AUTO).model
        == f"bedrock/converse/{region}/{prefix}{expected}"
    )
    assert discovery.create_client.call_args.args[0].region == region


def test_cache_is_scoped_to_region_credentials_and_preference(
    discovery, settings
):
    for model in discovery.models:
        model["inferenceTypesSupported"] = ["ON_DEMAND"]
    assert (
        bedrock_model_target(model=BedrockModel.CLAUDE_HAIKU_AUTO).model
        == bedrock_model_target(model=BedrockModel.CLAUDE_HAIKU_AUTO).model
    )
    discovery.create_client.assert_called_once()
    assert bedrock_model_target(
        model=BedrockModel.CLAUDE_HAIKU_4_5
    ).model.endswith(OLD_MODEL)
    settings.AWS_REGION = "eu-west-1"
    settings.BEDROCK_ALLOWED_GEOGRAPHY = "EU"
    assert (
        "/eu-west-1/"
        in bedrock_model_target(model=BedrockModel.CLAUDE_HAIKU_AUTO).model
    )
    settings.BEDROCK_API_KEY = "rotated-test-key"
    bedrock_model_target(model=BedrockModel.CLAUDE_HAIKU_AUTO)
    assert discovery.create_client.call_count == 4


def test_missing_region_fails_before_discovery_with_safe_service_error(
    discovery, settings
):
    settings.AWS_REGION = ""
    cache.set(
        SITE_CACHE_KEY, Site(assistant_model=BedrockModel.CLAUDE_HAIKU_AUTO)
    )
    request = RequestFactory().post("/", {"message": "Help"})
    request.identity = Mock()
    response = stream(request)
    assert response.status_code == 503
    assert b"temporarily unavailable" in response.content
    discovery.create_client.assert_not_called()


def test_geography_does_not_confuse_india_with_other_asia_pacific_regions(
    discovery, settings
):
    settings.AWS_REGION = "ap-south-1"
    settings.BEDROCK_ALLOWED_GEOGRAPHY = "IN"
    for profile in discovery.profiles:
        profile["inferenceProfileId"] = profile["inferenceProfileId"].replace(
            "us.", "apac."
        )
        for model in profile["models"]:
            model["modelArn"] = model["modelArn"].replace(
                "us-east-1", "ap-southeast-2"
            )
    with pytest.raises(BedrockModelUnavailable):
        bedrock_model_target(model=BedrockModel.CLAUDE_HAIKU_AUTO)


@pytest.mark.parametrize(
    "failure", ["denied", "no_route", "timestamp", "ambiguous"]
)
def test_discovery_fails_explicitly_and_does_not_cache_failures(
    discovery, failure
):
    if failure == "denied":
        discovery.client.list_foundation_models.side_effect = ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "provider-secret",
                }
            },
            "ListFoundationModels",
        )
    elif failure == "no_route":
        discovery.profiles.clear()
    elif failure == "timestamp":
        for model in discovery.models:
            model["modelLifecycle"].pop("startOfLifeTime")
    else:
        discovery.models[0]["modelLifecycle"] = discovery.models[1][
            "modelLifecycle"
        ].copy()
    for _ in range(2):
        with pytest.raises(BedrockModelUnavailable) as error:
            bedrock_model_target(model=BedrockModel.CLAUDE_HAIKU_AUTO)
        assert "provider-secret" not in str(error.value)
    assert discovery.create_client.call_count == 2


@pytest.mark.parametrize(
    ("preference", "older", "newer"),
    [
        ("tier/economy", "openai.gpt-5.6-luna", "openai.gpt-6-luna"),
        ("tier/balanced", "openai.gpt-5.6-terra", "openai.gpt-6.1-terra"),
        ("tier/best", "openai.gpt-5.6-sol", "openai.gpt-6.1-sol"),
        ("auto/zai.glm-flash", "zai.glm-4.7-flash", "zai.glm-5-flash"),
    ],
)
def test_automatic_selection_is_shared_across_model_classes(
    discovery, preference, older, newer
):
    for model, model_id in zip(discovery.models, (older, newer), strict=True):
        model["modelId"] = model_id
        model["inferenceTypesSupported"] = ["ON_DEMAND"]
    target = bedrock_model_target(model=preference)
    assert target.model.endswith(newer)
    assert target.region == "us-east-1"
    assert bedrock_model_target(model=target.model) == target


def test_regional_catalogs_and_native_capabilities_are_endpoint_specific(
    discovery,
):
    from lp_agent.adapters.bedrock_discovery import (
        discover_catalog,
        resolve_catalog,
    )
    from lp_agent.adapters.bedrock_models import BedrockPolicy

    model_id = "openai.gpt-6-luna"
    discovery.models[1]["modelId"] = model_id
    discovery.models[1]["inputModalities"].append("IMAGE")
    discovery.profiles[1]["inferenceProfileId"] = f"us.{model_id}"
    discovery.profiles[1]["models"][0]["modelArn"] = (
        f"arn:aws:bedrock:us-east-1::foundation-model/{model_id}"
    )
    discovery.mantle.models.list.return_value = [
        Mock(model_dump=Mock(return_value={"id": model_id, "created": 1}))
    ]
    policy = BedrockPolicy("us-east-1")
    required = frozenset({"text", "stream", "image", "continuation"})

    def resolve():
        return resolve_catalog(
            discover_catalog(discovery.client, policy, "test-key"),
            discovery.client,
            policy,
            "tier/economy",
            required,
        )

    assert "bedrock-mantle" in resolve().api_base
    discovery.models[1]["inferenceTypesSupported"] = ["ON_DEMAND"]
    target = resolve()
    assert "bedrock-runtime" in target.api_base
    assert target.native_responses and required <= target.capabilities
    discovery.models[1]["responseStreamingSupported"] = False
    assert "bedrock-mantle" in resolve().api_base
    discovery.mantle.models.list.return_value = []
    with pytest.raises(BedrockModelUnavailable):
        resolve()


def test_access_failure_refreshes_catalog_and_partial_catalogs_are_not_cached(
    discovery,
):
    from openai import APIConnectionError

    preference = BedrockModel.CLAUDE_HAIKU_AUTO
    bedrock_model_target(model=preference)
    bedrock_model_failed(SimpleNamespace(status_code=403))
    discovery.models.pop()
    assert bedrock_model_target(model=preference).model.endswith(OLD_MODEL)
    assert discovery.client.list_foundation_models.call_count == 2

    cache.clear()
    discovery.mantle.models.list.side_effect = APIConnectionError(
        request=Mock()
    )
    for _ in range(2):
        assert bedrock_model_target(model=preference).model.endswith(OLD_MODEL)
    assert discovery.client.list_foundation_models.call_count == 4


def test_standalone_environment_shares_discovery_for_model_and_judge(
    discovery, tmp_path
):
    from lp_agent.adapters.bedrock_models import BedrockPolicy
    from lp_agent.adapters.environment import create_environment

    with patch(
        "lp_agent.adapters.bedrock_discovery.bedrock_client",
        return_value=discovery.client,
    ):
        create_environment(
            identity_id="test-identity",
            resource_root=tmp_path,
            api_key="test-key",
            policy=BedrockPolicy("us-east-1"),
            model="auto/anthropic.haiku",
            judge="auto/anthropic.haiku",
        )
    discovery.client.list_foundation_models.assert_called_once()
    assert discovery.client.get_foundation_model_availability.call_count == 2


def test_cost_uses_bedrock_pricing_for_openai_compatible_transport():
    import litellm

    from lp_agent.adapters.bedrock_models import ResolvedBedrockModel

    billing_model = "bedrock_mantle/openai.gpt-99-luna"
    target = ResolvedBedrockModel(
        "openai/openai.gpt-99-luna",
        "us-east-1",
        billing_model=billing_model,
    )
    with patch.dict(
        litellm.model_cost,
        {
            billing_model: {
                "litellm_provider": "bedrock_mantle",
                "input_cost_per_token": 0.000001,
                "output_cost_per_token": 0.000002,
            }
        },
    ):
        assert target.completion_cost(
            {"prompt_tokens": 10, "completion_tokens": 7}
        ) == pytest.approx(0.000024)
