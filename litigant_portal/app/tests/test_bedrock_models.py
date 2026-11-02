from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from django.core.cache import cache
from django.test import RequestFactory

from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.models import ChatThread, Site
from litigant_portal.app.selectors.bedrock import (
    BedrockModelUnavailable,
    bedrock_model_choices,
    bedrock_model_failed,
    bedrock_model_target,
)
from litigant_portal.app.selectors.site import (
    site_get_model_target,
)
from litigant_portal.app.services.chat_engine import (
    chat_thread_generate_description,
)
from litigant_portal.app.views.assistant import stream

OLD_MODEL = "anthropic.claude-haiku-4-5-20251001-v1:0"
NEW_MODEL = "anthropic.claude-haiku-5-5"


def test_new_family_needs_only_mapping_and_tier_configuration(
    discovery, monkeypatch
):
    from litigant_portal.agents import bedrock as bedrock_models

    monkeypatch.setattr(
        bedrock_models,
        "MODEL_MAPPING",
        {"auto/anthropic.sonnet": "Claude Sonnet"},
        raising=False,
    )
    monkeypatch.setattr(
        bedrock_models,
        "MODEL_CHOICES",
        {"economy": ["Claude Sonnet"], "balanced": [], "best": []},
    )
    for model in discovery.models:
        model["modelId"] = model["modelId"].replace("haiku", "sonnet")
        model["inferenceTypesSupported"] = ["ON_DEMAND"]
    assert bedrock_models.model_class("anthropic.claude-sonnet-5-5") == (
        "anthropic.sonnet",
        "5.5",
    )
    assert bedrock_model_target(model="auto/anthropic.sonnet").model.endswith(
        "anthropic.claude-sonnet-5-5"
    )
    assert bedrock_model_choices() == (
        ("auto/anthropic.sonnet", "Claude Sonnet (economy)"),
    )


def test_available_choices_and_defaults_share_discovery_without_switching_saved_models(
    discovery,
):
    assert bedrock_model_choices() == (
        ("auto/anthropic.haiku", "Claude Haiku (economy)"),
    )
    assert site_get_model_target(role="fast").model.endswith(NEW_MODEL)
    with pytest.raises(BedrockModelUnavailable, match="Judging is disabled"):
        site_get_model_target(role="judge")
    with pytest.raises(BedrockModelUnavailable, match="No available balanced"):
        site_get_model_target(role="assistant")
    cache.set(SITE_CACHE_KEY, Site(fast_model="auto/openai.luna"))
    with pytest.raises(BedrockModelUnavailable):
        site_get_model_target(role="fast")


def test_account_access_checks_are_shared_across_role_resolutions(discovery):
    bedrock_model_choices(role="fast")
    bedrock_model_choices(role="assistant")
    bedrock_model_choices(role="judge")
    discovery.client.list_foundation_models.assert_called_once()
    assert discovery.client.get_foundation_model_availability.call_count == 2
    discovery.client.list_foundation_models.assert_called_once()


@pytest.mark.parametrize(
    "labels", [["Unknown"], ["GPT Luna", "GPT Luna"], ["GPT Terra"]]
)
def test_invalid_curation_fails_before_discovery(
    discovery, monkeypatch, labels
):
    from litigant_portal.agents.bedrock import MODEL_CHOICES

    monkeypatch.setitem(MODEL_CHOICES, "economy", labels)
    with pytest.raises(BedrockModelUnavailable, match="unknown or duplicate"):
        bedrock_model_choices()
    discovery.create_client.assert_not_called()


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
    [
        ("", NEW_MODEL),
        ("bedrock_mantle/anthropic.claude-haiku-4-5", OLD_MODEL),
    ],
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
        bedrock_model_target(model="auto/anthropic.haiku").model
        == f"bedrock/converse/{region}/{prefix}{expected}"
    )
    assert discovery.create_client.call_args.args[0].region == region


def test_cache_is_scoped_to_region_credentials_and_preference(
    discovery, settings
):
    for model in discovery.models:
        model["inferenceTypesSupported"] = ["ON_DEMAND"]
    assert (
        bedrock_model_target(model="auto/anthropic.haiku").model
        == bedrock_model_target(model="auto/anthropic.haiku").model
    )
    discovery.create_client.assert_called_once()
    assert bedrock_model_target(
        model="bedrock_mantle/anthropic.claude-haiku-4-5"
    ).model.endswith(OLD_MODEL)
    settings.AWS_REGION = "eu-west-1"
    settings.BEDROCK_ALLOWED_GEOGRAPHY = "EU"
    assert (
        "/eu-west-1/"
        in bedrock_model_target(model="auto/anthropic.haiku").model
    )
    settings.BEDROCK_API_KEY = "rotated-test-key"
    bedrock_model_target(model="auto/anthropic.haiku")
    assert discovery.create_client.call_count == 4


@pytest.mark.parametrize("preference", [None, "auto/anthropic.haiku"])
def test_missing_region_fails_before_discovery_with_safe_service_error(
    discovery, settings, preference
):
    settings.AWS_REGION = ""
    cache.set(SITE_CACHE_KEY, Site(assistant_model=preference))
    request = RequestFactory().post("/", {"message": "Help"})
    request.identity = Mock()
    with (
        patch(
            "litigant_portal.app.services.chat_engine.ChatThread.objects.create"
        ) as create_thread,
        patch(
            "litigant_portal.app.services.chat_engine.chat_message_create"
        ) as create_message,
    ):
        response = stream(request)
    create_thread.assert_not_called()
    create_message.assert_not_called()
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
        bedrock_model_target(model="auto/anthropic.haiku")


@pytest.mark.parametrize(
    "failure", ["denied", "availability", "no_route", "timestamp", "ambiguous"]
)
def test_discovery_fails_explicitly_and_does_not_cache_failures(
    discovery, failure
):
    if failure in {"denied", "availability"}:
        operation = (
            discovery.client.list_foundation_models
            if failure == "denied"
            else discovery.client.get_foundation_model_availability
        )
        operation.side_effect = ClientError(
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
            bedrock_model_target(model="auto/anthropic.haiku")
        assert "provider-secret" not in str(error.value)
    assert discovery.create_client.call_count == 2


@pytest.mark.parametrize(
    ("preference", "older", "newer"),
    [
        ("auto/openai.luna", "openai.gpt-5.6-luna", "openai.gpt-6-luna"),
        ("auto/openai.terra", "openai.gpt-5.6-terra", "openai.gpt-6.1-terra"),
        ("auto/openai.sol", "openai.gpt-5.6-sol", "openai.gpt-6.1-sol"),
        ("auto/zai.glm-flash", "zai.glm-4.7-flash", "zai.glm-5-flash"),
    ],
)
def test_automatic_selection_is_shared_across_model_classes(
    discovery, monkeypatch, preference, older, newer
):
    from litigant_portal.agents.bedrock import MODEL_CHOICES

    monkeypatch.setitem(MODEL_CHOICES, "best", ["GPT Sol", "GLM Flash"])
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
    from litigant_portal.agents.bedrock import BedrockPolicy
    from litigant_portal.app.selectors.bedrock import (
        discover_catalog,
        resolve_catalog,
    )

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
    required = frozenset({"text", "stream", "image"})

    def resolve():
        return resolve_catalog(
            discover_catalog(discovery.client, policy, "test-key"),
            discovery.client,
            policy,
            "auto/openai.luna",
            required,
        )

    assert "bedrock-mantle" in resolve().api_base
    discovery.models[1]["inferenceTypesSupported"] = ["ON_DEMAND"]
    target = resolve()
    assert target.model == f"bedrock/converse/us-east-1/{model_id}"
    assert required <= target.capabilities
    assert "auto/openai.luna" in dict(bedrock_model_choices(role="assistant"))
    discovery.models[1]["responseStreamingSupported"] = False
    cache.clear()
    assert "auto/openai.luna" not in dict(
        bedrock_model_choices(role="assistant")
    )
    assert "bedrock-mantle" in resolve().api_base
    discovery.mantle.models.list.return_value = []
    with pytest.raises(BedrockModelUnavailable):
        resolve()


@pytest.mark.parametrize(
    "part_type, required",
    [
        ("text", {"text"}),
        ("image_url", {"text", "image"}),
        ("file", {"text", "document"}),
    ],
)
def test_document_reader_uses_the_resolved_route_and_required_capabilities(
    discovery, part_type, required
):
    from io import BytesIO

    from litigant_portal.agents.bedrock import ResolvedBedrockModel
    from litigant_portal.agents.tools.query_document import QueryDocument

    target = ResolvedBedrockModel(
        "bedrock/converse/us-east-1/test", "us-east-1"
    )
    upload = SimpleNamespace(
        id="test",
        name="example",
        identity=Mock(),
        file=Mock(open=Mock(return_value=BytesIO(b"test"))),
    )
    with (
        patch(
            "litigant_portal.app.models.ChatThread.objects.get",
            return_value=SimpleNamespace(identity=upload.identity),
        ),
        patch(
            "litigant_portal.app.models.UserUpload.objects.filter"
        ) as uploads,
        patch(
            "litigant_portal.app.services.upload.user_upload_reader_limit_error",
            return_value=None,
        ),
        patch(
            "litigant_portal.app.services.upload.user_upload_content_part",
            return_value={"type": part_type},
        ),
        patch(
            "litigant_portal.app.selectors.site.site_get_model_target",
            return_value=target,
        ) as resolve,
        patch(
            "litellm.completion",
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=" Answer ")
                    )
                ],
                usage={},
            ),
        ) as complete,
        patch("litellm.completion_cost", return_value=0.01),
    ):
        uploads.return_value.first.return_value = upload
        output = QueryDocument(upload_id="test", request="Summarize")(
            thread_id="test"
        )
    resolve.assert_called_once_with(
        role="assistant", required=frozenset(required)
    )
    assert complete.call_args.kwargs["model"] == target.model
    assert complete.call_args.kwargs["aws_region_name"] == "us-east-1"
    assert output.result == "Answer" and output.cost == 0.01


def test_access_failure_refreshes_catalog_and_partial_catalogs_are_not_cached(
    discovery,
):
    from openai import APIConnectionError

    preference = "auto/anthropic.haiku"
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


def test_cost_uses_the_resolved_bedrock_billing_identity():
    import litellm

    from litigant_portal.agents.bedrock import ResolvedBedrockModel

    billing_model = "bedrock_mantle/openai.gpt-99-luna"
    target = ResolvedBedrockModel(
        "bedrock_mantle/us-east-1/openai.gpt-99-luna",
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


def test_default_fast_model_uses_a_compatible_title_route(discovery):
    thread = ChatThread()
    thread.save = Mock()
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Help"))],
        usage=None,
    )
    with (
        patch(
            "litigant_portal.app.services.chat_engine.chat_message_list",
            return_value=[],
        ),
        patch("litellm.completion", return_value=response) as completion,
        patch("litellm.completion_cost", return_value=0),
        patch(
            "litigant_portal.app.services.chat_engine.chat_message_inject_meta"
        ),
    ):
        chat_thread_generate_description(thread=thread)
    assert completion.call_args.kwargs["model"] != (
        "bedrock_mantle/anthropic.claude-haiku-4-5"
    )
