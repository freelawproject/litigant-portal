from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from django.core.cache import cache
from django.test import RequestFactory
from openai import APIConnectionError

from litigant_portal.agents import bedrock
from litigant_portal.agents.bedrock import (
    BedrockCatalog,
    BedrockModelUnavailable,
    BedrockPolicy,
    FoundationModel,
    InferenceProfile,
    MantleModel,
    resolve_catalog,
)
from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.models import ChatThread, Site
from litigant_portal.app.selectors.bedrock import (
    bedrock_model_choices,
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
def catalog():
    native = tuple(
        FoundationModel.model_validate(
            {
                "modelId": model_id,
                "inputModalities": ["TEXT", "IMAGE"],
                "outputModalities": ["TEXT"],
                "inferenceTypesSupported": ["INFERENCE_PROFILE"],
                "responseStreamingSupported": True,
                "modelLifecycle": {
                    "status": "ACTIVE",
                    "startOfLifeTime": datetime(year, 10, 1, tzinfo=UTC),
                },
            }
        )
        for model_id, year in ((OLD_MODEL, 2025), (NEW_MODEL, 2026))
    )
    profiles = tuple(
        InferenceProfile.model_validate(
            {
                "inferenceProfileId": f"us.{model.model_id}",
                "type": "SYSTEM_DEFINED",
                "status": "ACTIVE",
                "models": [
                    {
                        "modelArn": f"arn:aws:bedrock:us-east-1::foundation-model/{model.model_id}"
                    }
                ],
            }
        )
        for model in native
    )
    return BedrockCatalog(
        native,
        (),
        profiles,
        authorized_model_ids=frozenset({OLD_MODEL, NEW_MODEL}),
    )


@pytest.fixture
def loaded_catalog(catalog, settings, monkeypatch):
    settings.AWS_REGION = "us-east-1"
    settings.BEDROCK_ALLOWED_GEOGRAPHY = "US"
    settings.BEDROCK_API_KEY = "test-bedrock-key"
    load = Mock(return_value=catalog)
    monkeypatch.setattr(bedrock, "discover_catalog", load)
    return load


def test_non_us_geography_is_rejected():
    with pytest.raises(BedrockModelUnavailable, match="Only US"):
        BedrockPolicy("eu-west-1", "EU")
    with pytest.raises(BedrockModelUnavailable, match="US region"):
        BedrockPolicy("eu-west-1")


@pytest.mark.parametrize(
    "preference, older, newer",
    [
        ("auto/openai.luna", "openai.gpt-5.6-luna", "openai.gpt-6-luna"),
        ("auto/anthropic.haiku", OLD_MODEL, NEW_MODEL),
        ("auto/zai.glm-flash", "zai.glm-4.7-flash", "zai.glm-5-flash"),
    ],
)
def test_family_selection_preserves_version_pins(
    catalog, monkeypatch, preference, older, newer
):
    monkeypatch.setitem(
        bedrock.MODEL_CHOICES, "best", ["GPT Sol", "GLM Flash"]
    )
    catalog = replace(
        catalog,
        native=tuple(
            model.model_copy(
                update={
                    "model_id": model_id,
                    "inference_types": frozenset({"ON_DEMAND"}),
                }
            )
            for model, model_id in zip(
                catalog.native, (older, newer), strict=True
            )
        ),
        authorized_model_ids=frozenset({older, newer}),
    )
    policy = BedrockPolicy("us-east-1")
    assert resolve_catalog(catalog, policy, preference).model.endswith(newer)
    assert resolve_catalog(
        catalog, policy, f"bedrock_mantle/{older}"
    ).model.endswith(older)


@pytest.mark.parametrize(
    "scenario",
    [
        "regional",
        "profile",
        "global",
        "foreign",
        "denied",
        "inactive",
        "timestamp",
    ],
)
def test_us_route_eligibility(catalog, scenario):
    newest, profile = catalog.native[1], catalog.profiles[1]
    expected = f"us.{NEW_MODEL}"
    if scenario == "regional":
        newest = newest.model_copy(
            update={"inference_types": frozenset({"ON_DEMAND"})}
        )
        expected = NEW_MODEL
    elif scenario == "global":
        profile = profile.model_copy(update={"id": f"global.{NEW_MODEL}"})
    elif scenario == "foreign":
        destination = profile.models[0]
        profile = profile.model_copy(
            update={
                "models": (
                    destination.model_copy(
                        update={
                            "arn": destination.arn.replace(
                                "us-east-1", "eu-west-1"
                            )
                        }
                    ),
                )
            }
        )
    elif scenario == "denied":
        catalog = replace(catalog, authorized_model_ids=frozenset({OLD_MODEL}))
    elif scenario == "inactive":
        newest = newest.model_copy(update={"status": "LEGACY"})
    elif scenario == "timestamp":
        newest = newest.model_copy(update={"released": None})
    if scenario not in {"regional", "profile"}:
        expected = f"us.{OLD_MODEL}"
    catalog = replace(
        catalog,
        native=(catalog.native[0], newest),
        profiles=(catalog.profiles[0], profile),
    )
    target = resolve_catalog(
        catalog, BedrockPolicy("us-east-1"), "auto/anthropic.haiku"
    )
    assert target.model == f"bedrock/converse/us-east-1/{expected}"


def test_endpoint_capabilities_choose_a_compatible_route(catalog):
    model_id = "openai.gpt-6-luna"
    model = catalog.native[1].model_copy(update={"model_id": model_id})
    profile = catalog.profiles[1].model_copy(
        update={
            "id": f"us.{model_id}",
            "models": (
                catalog.profiles[1]
                .models[0]
                .model_copy(
                    update={
                        "arn": f"arn:aws:bedrock:us-east-1::foundation-model/{model_id}"
                    }
                ),
            ),
        }
    )
    catalog = replace(
        catalog,
        native=(model,),
        profiles=(profile,),
        mantle=(MantleModel(id=model_id, created=model.released),),
        authorized_model_ids=frozenset({model_id}),
    )
    policy = BedrockPolicy("us-east-1")
    preference = "auto/openai.luna"
    assert resolve_catalog(catalog, policy, preference).model.startswith(
        "bedrock_mantle/"
    )
    required = frozenset({"text", "stream", "tools", "image"})
    assert resolve_catalog(
        catalog, policy, preference, required
    ).model.startswith("bedrock/converse/")
    catalog = replace(
        catalog, native=(model.model_copy(update={"streaming": False}),)
    )
    with pytest.raises(BedrockModelUnavailable):
        resolve_catalog(catalog, policy, preference, required)
    with pytest.raises(BedrockModelUnavailable):
        resolve_catalog(catalog, policy, preference, frozenset({"document"}))


@pytest.mark.parametrize(
    "failure", [None, "native", "availability", "denied", "mantle", "schema"]
)
def test_discovery_validates_and_loads_access_once(
    catalog, monkeypatch, failure
):
    client = Mock(
        spec=[
            "list_foundation_models",
            "get_paginator",
            "get_foundation_model_availability",
            "close",
        ]
    )
    payload = [
        model.model_dump(by_alias=True, exclude={"status", "released"})
        | {
            "modelLifecycle": {
                "status": model.status,
                "startOfLifeTime": model.released,
            },
        }
        for model in catalog.native
    ]
    client.list_foundation_models.return_value = {"modelSummaries": payload}
    client.get_paginator.return_value.paginate.return_value = [
        {
            "inferenceProfileSummaries": [
                profile.model_dump(by_alias=True)
                for profile in catalog.profiles
            ],
        }
    ]
    client.get_foundation_model_availability.return_value = {
        "authorizationStatus": "AUTHORIZED",
        "entitlementAvailability": "AVAILABLE",
        "regionAvailability": "AVAILABLE",
        "agreementAvailability": {"status": "AVAILABLE"},
    }
    monkeypatch.setattr(bedrock, "_bedrock_client", Mock(return_value=client))
    with patch("openai.OpenAI") as mantle:
        mantle.return_value.__enter__.return_value.models.list.return_value = []
        if failure in {"native", "availability"}:
            operation = (
                client.list_foundation_models
                if failure == "native"
                else client.get_foundation_model_availability
            )
            operation.side_effect = ClientError(
                {
                    "Error": {
                        "Code": "AccessDeniedException",
                        "Message": "provider-secret",
                    }
                },
                "Discovery",
            )
        elif failure == "schema":
            payload[0]["modelLifecycle"]["startOfLifeTime"] = "invalid-time"
        elif failure == "denied":
            available = client.get_foundation_model_availability.return_value
            client.get_foundation_model_availability.side_effect = (
                lambda *, modelId: {
                    **available,
                    "agreementAvailability": {
                        "status": "NOT_AVAILABLE"
                        if modelId == NEW_MODEL
                        else "AVAILABLE"
                    },
                }
            )
        elif failure == "mantle":
            mantle.return_value.__enter__.return_value.models.list.side_effect = APIConnectionError(
                request=Mock()
            )
        if failure in {"native", "availability", "schema"}:
            with pytest.raises(BedrockModelUnavailable) as error:
                bedrock.discover_catalog(
                    BedrockPolicy("us-east-1"), "test-key"
                )
            assert "provider-secret" not in str(error.value)
        else:
            snapshot = bedrock.discover_catalog(
                BedrockPolicy("us-east-1"), "test-key"
            )
            assert snapshot.authorized_model_ids == (
                frozenset({OLD_MODEL})
                if failure == "denied"
                else catalog.authorized_model_ids
            )
            assert snapshot.complete == (failure != "mantle")
            for required in (
                frozenset({"text"}),
                frozenset({"text", "stream", "tools"}),
            ):
                resolve_catalog(
                    snapshot,
                    BedrockPolicy("us-east-1"),
                    "auto/anthropic.haiku",
                    required,
                )
            assert client.get_foundation_model_availability.call_count == 2
    client.close.assert_called_once()


def test_catalog_cache_is_shared_scoped_and_invalidated(
    loaded_catalog, settings, monkeypatch
):
    for role in ("fast", "assistant", "judge"):
        bedrock_model_choices(role=role)
    bedrock_model_target(model=f"bedrock_mantle/{OLD_MODEL}")
    loaded_catalog.assert_called_once()
    settings.AWS_REGION = "us-west-2"
    assert (
        "/us-west-2/"
        in bedrock_model_target(model="auto/anthropic.haiku").model
    )
    settings.BEDROCK_API_KEY = "rotated-test-key"
    bedrock_model_target(model="auto/anthropic.haiku")
    monkeypatch.setitem(bedrock.MODEL_CHOICES, "best", [])
    bedrock_model_target(model="auto/anthropic.haiku")
    assert loaded_catalog.call_count == 4
    loaded_catalog.return_value = replace(
        loaded_catalog.return_value,
        authorized_model_ids=frozenset({OLD_MODEL}),
    )
    bedrock_model_failed(SimpleNamespace(status_code=403))
    assert bedrock_model_target(model="auto/anthropic.haiku").model.endswith(
        OLD_MODEL
    )
    assert loaded_catalog.call_count == 5


@pytest.mark.parametrize("incomplete", [False, True])
def test_failed_or_incomplete_discovery_is_not_cached(
    loaded_catalog, incomplete
):
    if incomplete:
        loaded_catalog.return_value = replace(
            loaded_catalog.return_value, complete=False
        )
        for _ in range(2):
            bedrock_model_target(model="auto/anthropic.haiku")
    else:
        loaded_catalog.side_effect = BedrockModelUnavailable(
            "Discovery failed."
        )
        for _ in range(2):
            with pytest.raises(BedrockModelUnavailable):
                bedrock_model_target(model="auto/anthropic.haiku")
    assert loaded_catalog.call_count == 2


def test_invalid_configuration_fails_before_discovery_without_creating_a_thread(
    loaded_catalog, settings
):
    settings.AWS_REGION = ""
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
        assert stream(request).status_code == 503
    create_thread.assert_not_called()
    create_message.assert_not_called()
    loaded_catalog.assert_not_called()


@pytest.mark.parametrize(
    ("preference", "model_id"),
    [
        ("", NEW_MODEL),
        ("bedrock_mantle/anthropic.claude-haiku-4-5", OLD_MODEL),
    ],
)
def test_description_uses_discovered_model_and_books_usage(
    loaded_catalog, preference, model_id
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
    "part_type, required",
    [
        ("text", {"text"}),
        ("image_url", {"text", "image"}),
        ("file", {"text", "document"}),
    ],
)
def test_document_reader_uses_the_resolved_route_and_required_capabilities(
    part_type, required
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
