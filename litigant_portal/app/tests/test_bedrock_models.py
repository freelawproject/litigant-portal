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
    bedrock_haiku_model,
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
    with patch("boto3.client", return_value=client) as create_client:
        yield SimpleNamespace(
            client=client,
            models=models,
            profiles=profiles,
            create_client=create_client,
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
        bedrock_haiku_model()
        == f"bedrock/converse/{region}/{prefix}{expected}"
    )
    assert discovery.create_client.call_args.kwargs["region_name"] == region


def test_cache_is_scoped_to_region_credentials_and_preference(
    discovery, settings
):
    for model in discovery.models:
        model["inferenceTypesSupported"] = ["ON_DEMAND"]
    assert bedrock_haiku_model() == bedrock_haiku_model()
    discovery.create_client.assert_called_once()
    assert bedrock_haiku_model(version="4.5").endswith(OLD_MODEL)
    settings.AWS_REGION = "eu-west-1"
    assert "/eu-west-1/" in bedrock_haiku_model()
    settings.BEDROCK_API_KEY = "rotated-test-key"
    bedrock_haiku_model()
    assert discovery.create_client.call_count == 4


def test_missing_region_fails_before_discovery_with_safe_service_error(
    discovery, settings
):
    settings.AWS_REGION = ""
    cache.set(
        SITE_CACHE_KEY, Site(assistant_model=BedrockModel.CLAUDE_HAIKU_AUTO)
    )
    response = stream(RequestFactory().post("/", {"message": "Help"}))
    assert response.status_code == 503
    assert b"temporarily unavailable" in response.content
    discovery.create_client.assert_not_called()


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
        discovery.models[1]["modelLifecycle"].pop("startOfLifeTime")
    else:
        discovery.profiles.append(
            {
                **discovery.profiles[1],
                "inferenceProfileId": f"alternative.{NEW_MODEL}",
            }
        )
    for _ in range(2):
        with pytest.raises(BedrockModelUnavailable) as error:
            bedrock_haiku_model()
        assert "provider-secret" not in str(error.value)
    assert discovery.create_client.call_count == 2
