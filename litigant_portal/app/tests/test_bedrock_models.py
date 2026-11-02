from dataclasses import replace
from datetime import UTC, datetime
from time import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from django.core.cache import cache
from django.core.files.base import ContentFile
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
    ResolvedBedrockModel,
    resolve_catalog,
)
from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.models import (
    ChatThread,
    Site,
    UserIdentity,
    UserUpload,
)
from litigant_portal.app.selectors.bedrock import (
    bedrock_model_choices,
    bedrock_model_target,
)
from litigant_portal.app.services import chat_engine as engine
from litigant_portal.app.services.bedrock import (
    bedrock_catalog_invalidate_on_error,
)
from litigant_portal.app.views.assistant import stream

OLD_MODEL = "anthropic.claude-haiku-4-5-20251001-v1:0"
NEW_MODEL = "anthropic.claude-haiku-5-5"


def _native_payload(
    model_id: str,
    year: int = 2026,
    *,
    inference_type: str = "INFERENCE_PROFILE",
) -> dict:
    return {
        "modelId": model_id,
        "inputModalities": ["TEXT", "IMAGE"],
        "outputModalities": ["TEXT"],
        "inferenceTypesSupported": [inference_type],
        "responseStreamingSupported": True,
        "modelLifecycle": {
            "status": "ACTIVE",
            "startOfLifeTime": datetime(year, 10, 1, tzinfo=UTC),
        },
    }


def _profile_payload(
    model_id: str, *, prefix: str = "us", region: str = "us-east-1"
) -> dict:
    return {
        "inferenceProfileId": f"{prefix}.{model_id}",
        "type": "SYSTEM_DEFINED",
        "status": "ACTIVE",
        "models": [
            {
                "modelArn": f"arn:aws:bedrock:{region}::foundation-model/{model_id}"
            }
        ],
    }


@pytest.fixture
def catalog_payloads():
    native = [_native_payload(OLD_MODEL, 2025), _native_payload(NEW_MODEL)]
    return native, [_profile_payload(model["modelId"]) for model in native]


@pytest.fixture
def catalog(catalog_payloads):
    native, profiles = catalog_payloads
    return BedrockCatalog(
        tuple(FoundationModel.model_validate(model) for model in native),
        (),
        tuple(
            InferenceProfile.model_validate(profile) for profile in profiles
        ),
        authorized_model_ids=frozenset(model["modelId"] for model in native),
    )


@pytest.fixture
def loaded_catalog(catalog, settings, monkeypatch):
    settings.AWS_REGION = "us-east-1"
    settings.BEDROCK_ALLOWED_GEOGRAPHY = "US"
    settings.BEDROCK_API_KEY = "test-bedrock-key"
    load = Mock(return_value=catalog)
    monkeypatch.setattr(bedrock, "discover_catalog", load)
    return load


@pytest.fixture
def clock(monkeypatch):
    now = Mock(return_value=time())
    monkeypatch.setattr("django.core.cache.backends.base.time.time", now)
    return now


@pytest.fixture
def reader_catalog(loaded_catalog):
    terra = FoundationModel.model_validate(
        _native_payload("openai.gpt-5.6-terra", inference_type="ON_DEMAND")
    )
    loaded_catalog.return_value = replace(
        loaded_catalog.return_value,
        native=(*loaded_catalog.return_value.native, terra),
        authorized_model_ids=loaded_catalog.return_value.authorized_model_ids
        | {terra.model_id},
    )
    return loaded_catalog


@pytest.fixture
def completion(monkeypatch):
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content=" Name Change Help "),
                finish_reason="stop",
            )
        ],
        usage=SimpleNamespace(total_tokens=16),
    )
    complete = Mock(return_value=response)
    monkeypatch.setattr("litellm.completion", complete)
    monkeypatch.setattr("litellm.completion_cost", Mock(return_value=0.001))
    return complete


@pytest.fixture
def title_thread(monkeypatch):
    thread = ChatThread()
    thread.save = Mock()
    monkeypatch.setattr(
        engine,
        "chat_message_list",
        Mock(
            return_value=[
                SimpleNamespace(data={"role": "user", "content": "Help"})
            ],
        ),
    )
    inject = Mock()
    monkeypatch.setattr(engine, "chat_message_inject_meta", inject)
    return thread, inject


@pytest.fixture
def upload():
    return UserUpload(
        identity=UserIdentity(),
        name="example",
        size=4,
        pages=1,
        text_chars=4,
        file=ContentFile(b"test", name="example"),
    )


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
            FoundationModel.model_validate(
                _native_payload(model_id, year, inference_type="ON_DEMAND")
            )
            for model_id, year in ((older, 2025), (newer, 2026))
        ),
        authorized_model_ids=frozenset({older, newer}),
    )
    policy = BedrockPolicy("us-east-1")
    assert resolve_catalog(catalog, policy, preference).model.endswith(newer)
    assert resolve_catalog(
        catalog, policy, f"bedrock_mantle/{older}"
    ).model.endswith(older)


@pytest.mark.parametrize(
    "native_updates, profile_updates, authorized, expected",
    [
        ({"inference_types": frozenset({"ON_DEMAND"})}, {}, None, NEW_MODEL),
        ({}, {}, None, f"us.{NEW_MODEL}"),
        ({}, {"prefix": "global"}, None, f"us.{OLD_MODEL}"),
        ({}, {"region": "eu-west-1"}, None, f"us.{OLD_MODEL}"),
        ({}, {}, {OLD_MODEL}, f"us.{OLD_MODEL}"),
        ({"status": "LEGACY"}, {}, None, f"us.{OLD_MODEL}"),
        ({"released": None}, {}, None, f"us.{OLD_MODEL}"),
    ],
    ids=[
        "regional",
        "profile",
        "global",
        "foreign",
        "denied",
        "inactive",
        "timestamp",
    ],
)
def test_us_route_eligibility(
    catalog, native_updates, profile_updates, authorized, expected
):
    catalog = replace(
        catalog,
        native=(
            catalog.native[0],
            catalog.native[1].model_copy(update=native_updates),
        ),
        profiles=(
            catalog.profiles[0],
            InferenceProfile.model_validate(
                _profile_payload(NEW_MODEL, **profile_updates)
            ),
        ),
        authorized_model_ids=catalog.authorized_model_ids
        if authorized is None
        else frozenset(authorized),
    )
    target = resolve_catalog(
        catalog, BedrockPolicy("us-east-1"), "auto/anthropic.haiku"
    )
    assert target.model == f"bedrock/converse/us-east-1/{expected}"


def test_endpoint_capabilities_choose_a_compatible_route(catalog):
    model_id = "openai.gpt-6-luna"
    model = FoundationModel.model_validate(_native_payload(model_id))
    catalog = replace(
        catalog,
        native=(model,),
        profiles=(
            InferenceProfile.model_validate(_profile_payload(model_id)),
        ),
        mantle=(MantleModel(id=model_id, created=model.released),),
        authorized_model_ids=frozenset({model_id}),
    )
    policy, preference = BedrockPolicy("us-east-1"), "auto/openai.luna"
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


@pytest.fixture
def discovery_clients(catalog_payloads, monkeypatch):
    client = Mock(
        spec=[
            "list_foundation_models",
            "get_paginator",
            "get_foundation_model_availability",
            "close",
        ]
    )
    payload, profiles = catalog_payloads
    client.list_foundation_models.return_value = {"modelSummaries": payload}
    client.get_paginator.return_value.paginate.return_value = [
        {"inferenceProfileSummaries": profiles}
    ]
    client.get_foundation_model_availability.return_value = {
        "authorizationStatus": "AUTHORIZED",
        "entitlementAvailability": "AVAILABLE",
        "regionAvailability": "AVAILABLE",
        "agreementAvailability": {"status": "AVAILABLE"},
    }
    monkeypatch.setattr(bedrock, "_bedrock_client", Mock(return_value=client))
    with patch("openai.OpenAI") as mantle:
        models = mantle.return_value.__enter__.return_value.models.list
        models.return_value = []
        yield client, models, payload
    client.close.assert_called_once()


def test_discovery_loads_access_once(catalog, discovery_clients):
    client, _, _ = discovery_clients
    snapshot = bedrock.discover_catalog(BedrockPolicy("us-east-1"), "test-key")
    assert snapshot.complete
    assert snapshot.authorized_model_ids == catalog.authorized_model_ids
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


def test_discovery_excludes_denied_models(discovery_clients):
    client, _, _ = discovery_clients
    available = client.get_foundation_model_availability.return_value
    client.get_foundation_model_availability.side_effect = [
        available,
        available | {"agreementAvailability": {"status": "NOT_AVAILABLE"}},
    ]
    snapshot = bedrock.discover_catalog(BedrockPolicy("us-east-1"), "test-key")
    assert snapshot.complete
    assert snapshot.authorized_model_ids == frozenset({OLD_MODEL})


def test_mantle_failure_retains_a_partial_native_catalog(
    catalog, discovery_clients
):
    _, models, _ = discovery_clients
    models.side_effect = APIConnectionError(request=Mock())
    snapshot = bedrock.discover_catalog(BedrockPolicy("us-east-1"), "test-key")
    assert not snapshot.complete
    assert snapshot.native == catalog.native
    assert snapshot.authorized_model_ids == catalog.authorized_model_ids


@pytest.mark.parametrize(
    "operation",
    ["list_foundation_models", "get_foundation_model_availability"],
)
def test_discovery_provider_errors_are_sanitized(discovery_clients, operation):
    client, _, _ = discovery_clients
    getattr(client, operation).side_effect = ClientError(
        {
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "provider-secret",
            }
        },
        "Discovery",
    )
    with pytest.raises(BedrockModelUnavailable) as error:
        bedrock.discover_catalog(BedrockPolicy("us-east-1"), "test-key")
    assert "ClientError" in str(error.value)
    assert "provider-secret" not in str(error.value)


def test_discovery_rejects_malformed_metadata(discovery_clients):
    _, _, payload = discovery_clients
    payload[0]["modelLifecycle"]["startOfLifeTime"] = "invalid-time"
    with pytest.raises(BedrockModelUnavailable, match="ValidationError"):
        bedrock.discover_catalog(BedrockPolicy("us-east-1"), "test-key")


def test_catalog_cache_is_shared_and_scoped(
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


def test_partial_discovery_cache_expires_after_five_minutes(
    loaded_catalog, clock
):
    loaded_catalog.return_value = replace(
        loaded_catalog.return_value, complete=False
    )
    for _ in range(2):
        bedrock_model_target(model="auto/anthropic.haiku")
    loaded_catalog.assert_called_once()
    clock.return_value += 301
    bedrock_model_target(model="auto/anthropic.haiku")
    assert loaded_catalog.call_count == 2


def test_discovery_failure_cache_expires_and_sanitizes_errors(
    loaded_catalog, clock
):
    loaded_catalog.side_effect = BedrockModelUnavailable("provider-secret")
    for _ in range(2):
        with pytest.raises(BedrockModelUnavailable) as error:
            bedrock_model_target(model="auto/anthropic.haiku")
        assert "provider-secret" not in str(error.value)
    loaded_catalog.assert_called_once()
    clock.return_value += 301
    with pytest.raises(BedrockModelUnavailable):
        bedrock_model_target(model="auto/anthropic.haiku")
    assert loaded_catalog.call_count == 2


def test_complete_catalog_lasts_one_hour(loaded_catalog, clock):
    bedrock_model_target(model="auto/anthropic.haiku")
    clock.return_value += 301
    bedrock_model_target(model="auto/anthropic.haiku")
    loaded_catalog.assert_called_once()
    clock.return_value += 3300
    bedrock_model_target(model="auto/anthropic.haiku")
    assert loaded_catalog.call_count == 2


@pytest.mark.parametrize(
    "status, discoveries", [(400, 1), (401, 2), (403, 2), (404, 2)]
)
def test_inference_errors_invalidate_only_access_metadata(
    loaded_catalog, status, discoveries
):
    bedrock_model_target(model="auto/anthropic.haiku")
    loaded_catalog.return_value = replace(
        loaded_catalog.return_value,
        authorized_model_ids=frozenset({OLD_MODEL}),
    )
    bedrock_catalog_invalidate_on_error(SimpleNamespace(status_code=status))
    target = bedrock_model_target(model="auto/anthropic.haiku")
    assert target.model.endswith(OLD_MODEL if discoveries == 2 else NEW_MODEL)
    assert loaded_catalog.call_count == discoveries


def test_model_choice_labels_include_the_resolved_version(loaded_catalog):
    assert bedrock_model_choices() == (
        ("auto/anthropic.haiku", "Claude Haiku 5.5 (Economy)"),
    )


def test_model_choices_reuse_the_supplied_catalog(catalog, loaded_catalog):
    assert bedrock_model_choices(role="assistant", catalog=catalog) == (
        ("auto/anthropic.haiku", "Claude Haiku 5.5 (Economy)"),
    )
    assert bedrock_model_choices(catalog=BedrockCatalog((), (), ())) == ()
    loaded_catalog.assert_not_called()


@pytest.mark.parametrize(
    "selected, required, expected",
    [
        ("auto/openai.terra", frozenset({"text", "document"}), NEW_MODEL),
        (
            "auto/openai.terra",
            frozenset({"text", "image"}),
            "openai.gpt-5.6-terra",
        ),
        ("auto/anthropic.haiku", frozenset({"text", "document"}), NEW_MODEL),
    ],
)
def test_reader_prefers_a_capable_assistant_then_falls_back(
    reader_catalog, selected, required, expected
):
    from litigant_portal.app.selectors.site import site_get_reader_model_target

    site = Site(assistant_model=selected)
    cache.set(SITE_CACHE_KEY, site)
    target = site_get_reader_model_target(required=required)
    assert target.model.endswith(expected)
    assert site.assistant_model == selected


@pytest.mark.parametrize("content_type", ["application/pdf", "image/png"])
def test_hydration_stubs_unsupported_native_parts(content_type, upload):
    from litigant_portal.app.services.upload import user_upload_llm_parts

    upload.content_type = content_type
    upload_id = str(upload.id)
    parts = user_upload_llm_parts(
        history=[
            {"role": "user", "content": "Read", "attachments": [upload_id]}
        ],
        cache={"uploads": {upload_id: upload}},
        capabilities=frozenset({"text"}),
    )
    assert parts[0][1]["type"] == "text"
    assert "query_document" in parts[0][1]["text"]


def test_reader_reports_when_no_enabled_model_is_capable(loaded_catalog):
    from litigant_portal.app.selectors.site import site_get_reader_model_target

    loaded_catalog.return_value = replace(
        loaded_catalog.return_value, authorized_model_ids=frozenset()
    )
    with pytest.raises(
        BedrockModelUnavailable, match="No enabled reader model"
    ):
        site_get_reader_model_target(required=frozenset({"text", "document"}))


@pytest.mark.parametrize(
    "content, finish_reason", [("", "stop"), ("Partial", "length")]
)
def test_gpt_title_budget_and_empty_or_truncated_diagnostics(
    title_thread, completion, monkeypatch, content, finish_reason, caplog
):
    target = ResolvedBedrockModel(
        "bedrock/converse/us-east-1/us.openai.gpt-5.6-luna",
        "us-east-1",
        billing_model="us.openai.gpt-5.6-luna",
    )
    monkeypatch.setattr(
        engine, "site_get_model_target", lambda **kwargs: target
    )
    choice = completion.return_value.choices[0]
    choice.message.content, choice.finish_reason = content, finish_reason
    thread, _ = title_thread
    assert engine.chat_thread_generate_description(thread=thread) == content
    assert completion.call_args.kwargs["max_tokens"] == 1024
    assert completion.call_args.kwargs["reasoning_effort"] == "low"
    completion.assert_called_once()
    assert "Thread title empty or truncated" in caplog.text
    assert bool(thread.save.call_count) == bool(content)


def test_invalid_configuration_fails_before_discovery_without_creating_a_thread(
    loaded_catalog, settings
):
    settings.AWS_REGION = ""
    request = RequestFactory().post("/", {"message": "Help"})
    request.identity = Mock()
    with (
        patch.object(ChatThread.objects, "create") as create_thread,
        patch.object(engine, "chat_message_create") as create_message,
    ):
        assert stream(request).status_code == 503
    create_thread.assert_not_called()
    create_message.assert_not_called()
    loaded_catalog.assert_not_called()


def test_chat_service_preserves_explicit_evaluation_pins(loaded_catalog):
    from litigant_portal.agents.base import Agent

    with (
        patch.object(
            ChatThread.objects,
            "create",
            side_effect=RuntimeError("stop after resolution"),
        ) as create,
        pytest.raises(RuntimeError, match="stop after resolution"),
    ):
        engine.chat_stream(
            identity=Mock(),
            message="Help",
            agent_class=Agent,
            thread_type="evaluation",
            model=f"bedrock_mantle/{OLD_MODEL}",
        )
    create.assert_called_once()
    loaded_catalog.assert_called_once()


@pytest.mark.parametrize(
    ("preference", "model_id"),
    [
        ("", NEW_MODEL),
        ("bedrock_mantle/anthropic.claude-haiku-4-5", OLD_MODEL),
    ],
)
def test_description_uses_discovered_model_and_books_usage(
    loaded_catalog, title_thread, completion, preference, model_id
):
    cache.set(SITE_CACHE_KEY, Site(fast_model=preference))
    thread, inject_meta = title_thread
    assert (
        engine.chat_thread_generate_description(thread=thread)
        == "Name Change Help"
    )
    resolved = f"bedrock/converse/us-east-1/us.{model_id}"
    assert completion.call_args.kwargs["model"] == resolved
    assert completion.call_args.kwargs["max_tokens"] == 1024
    assert "reasoning_effort" not in completion.call_args.kwargs
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
    "content_type, part_type, expected",
    [
        ("text/plain", "text", "openai.gpt-5.6-terra"),
        ("image/png", "image_url", "openai.gpt-5.6-terra"),
        ("application/pdf", "file", NEW_MODEL),
    ],
)
def test_document_reader_uses_the_resolved_route_and_required_capabilities(
    reader_catalog,
    upload,
    completion,
    monkeypatch,
    content_type,
    part_type,
    expected,
):
    from litigant_portal.agents.tools.query_document import QueryDocument

    cache.set(SITE_CACHE_KEY, Site(assistant_model="auto/openai.terra"))
    upload.content_type = content_type
    monkeypatch.setattr(
        ChatThread.objects,
        "get",
        Mock(return_value=ChatThread(identity=upload.identity)),
    )
    uploads = Mock(return_value=Mock(first=Mock(return_value=upload)))
    monkeypatch.setattr(UserUpload.objects, "filter", uploads)
    completion.return_value.choices[0].message.content = " Answer "
    output = QueryDocument(upload_id=str(upload.id), request="Summarize")(
        thread_id="test"
    )
    uploads.assert_called_once_with(
        id=str(upload.id), identity=upload.identity
    )
    args = completion.call_args.kwargs
    assert args["model"].endswith(expected)
    assert args["aws_region_name"] == "us-east-1"
    assert args["messages"][1]["content"][-1]["type"] == part_type
    assert output.result == "Answer" and output.cost == 0.001


def test_cost_uses_the_resolved_bedrock_billing_identity():
    import litellm

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
