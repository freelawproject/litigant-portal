from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from threading import Event
from time import time
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError, ReadTimeoutError
from django.core.cache import cache, caches
from django.core.files.base import ContentFile
from django.test import RequestFactory
from openai import APIConnectionError

from litigant_portal.agents import bedrock
from litigant_portal.agents.bedrock import (
    BedrockCatalog,
    BedrockDiscoveryError,
    BedrockModelUnavailable,
    BedrockPolicy,
    FoundationModel,
    InferenceProfile,
    MantleModel,
    ResolvedBedrockModel,
    resolve_catalog,
)
from litigant_portal.app.cache import SITE_CACHE_KEY, bedrock_catalog_cache_key
from litigant_portal.app.models import (
    ChatThread,
    Site,
    UserIdentity,
    UserUpload,
)
from litigant_portal.app.selectors.bedrock import (
    bedrock_model_choices,
    bedrock_model_target,
    bedrock_policy,
)
from litigant_portal.app.services import chat_engine as engine
from litigant_portal.app.services.bedrock import (
    bedrock_catalog_invalidate_on_error,
)
from litigant_portal.app.views.assistant import stream

OLD_MODEL = "anthropic.claude-haiku-4-5-20251001-v1:0"
NEW_MODEL = "anthropic.claude-haiku-5-5"
GPT_MODEL = "openai.gpt-99-luna"


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
def configured_bedrock(settings):
    settings.AWS_REGION = "us-east-1"
    settings.BEDROCK_ALLOWED_GEOGRAPHY = "US"
    settings.BEDROCK_API_KEY = "test-bedrock-key"


@pytest.fixture
def loaded_catalog(catalog, configured_bedrock, monkeypatch):
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
        content_type="text/plain",
        size=4,
        pages=1,
        text_chars=4,
        file=ContentFile(b"test", name="example"),
    )


@pytest.fixture
def reader_tool(reader_catalog, upload, monkeypatch):
    from litigant_portal.agents.tools.query_document import QueryDocument

    cache.set(SITE_CACHE_KEY, Site(assistant_model="auto/openai.terra"))
    monkeypatch.setattr(
        ChatThread.objects,
        "get",
        Mock(return_value=ChatThread(identity=upload.identity)),
    )
    uploads = Mock(return_value=Mock(first=Mock(return_value=upload)))
    monkeypatch.setattr(UserUpload.objects, "filter", uploads)
    return QueryDocument(
        upload_id=str(upload.id), request="Summarize"
    ), uploads


def test_defaults_fall_back_only_to_cheaper_tiers(monkeypatch):
    monkeypatch.setattr(
        bedrock,
        "model_tiers",
        lambda: {
            "cheap": "economy",
            "preferred": "balanced",
            "premium": "best",
        },
    )
    assert bedrock.default_model("assistant", {"cheap", "premium"}) == "cheap"
    with pytest.raises(BedrockModelUnavailable):
        bedrock.default_model("assistant", {"premium"})
    with pytest.raises(BedrockModelUnavailable):
        bedrock.default_model("fast", {"preferred", "premium"})


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
    catalog, preference, older, newer
):
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
    assert client.close.call_count == client.list_foundation_models.call_count


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
    assert "AccessDeniedException" in str(error.value)
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


@pytest.mark.parametrize(
    "complete, refresh_after", [(True, 55 * 60), (False, 4 * 60)]
)
def test_catalog_refreshes_before_expiry(
    loaded_catalog, clock, complete, refresh_after
):
    loaded_catalog.return_value = replace(
        loaded_catalog.return_value, complete=complete
    )
    bedrock_model_target(model="auto/anthropic.haiku")
    clock.return_value += refresh_after - 1
    bedrock_model_target(model="auto/anthropic.haiku")
    loaded_catalog.assert_called_once()
    clock.return_value += 2
    bedrock_model_target(model="auto/anthropic.haiku")
    assert loaded_catalog.call_count == 2


@pytest.mark.parametrize(
    "provider_error, code",
    [
        (
            ClientError(
                {
                    "Error": {
                        "Code": "AccessDeniedException",
                        "Message": "provider-secret",
                    }
                },
                "Discovery",
            ),
            "AccessDeniedException",
        ),
        (
            ClientError(
                {
                    "Error": {
                        "Code": "ThrottlingException",
                        "Message": "provider-secret",
                    }
                },
                "Discovery",
            ),
            "ThrottlingException",
        ),
        (
            ReadTimeoutError(
                endpoint_url="https://example.test/provider-secret"
            ),
            "ReadTimeoutError",
        ),
    ],
)
def test_discovery_failure_cache_expires_and_sanitizes_errors(
    discovery_clients, configured_bedrock, clock, caplog, provider_error, code
):
    client, _, _ = discovery_clients
    client.list_foundation_models.side_effect = provider_error
    for _ in range(2):
        with pytest.raises(BedrockDiscoveryError, match=code):
            bedrock_model_target(model="auto/anthropic.haiku")
    assert client.list_foundation_models.call_count == 1
    assert "provider-secret" not in caplog.text
    assert caplog.text.count(f"Bedrock discovery failed ({code})") == 1
    entry = cache.get(bedrock_catalog_cache_key(bedrock_policy()))
    assert entry.value == code
    clock.return_value += 61
    with pytest.raises(BedrockDiscoveryError, match=code):
        bedrock_model_target(model="auto/anthropic.haiku")
    assert client.list_foundation_models.call_count == 2


@pytest.mark.parametrize("elapsed", [55 * 60 + 1, 60 * 60 + 1])
def test_failed_refresh_does_not_reuse_a_previous_catalog(
    loaded_catalog, clock, elapsed
):
    bedrock_model_target(model="auto/anthropic.haiku")
    loaded_catalog.side_effect = BedrockDiscoveryError("ThrottlingException")
    clock.return_value += elapsed
    for _ in range(2):
        with pytest.raises(BedrockDiscoveryError, match="ThrottlingException"):
            bedrock_model_target(model="auto/anthropic.haiku")
    assert loaded_catalog.call_count == 2


def test_failed_refresh_supersedes_a_previously_read_catalog(
    loaded_catalog, clock, monkeypatch
):
    bedrock_model_target(model="auto/anthropic.haiku")
    bedrock_catalog_invalidate_on_error(SimpleNamespace(status_code=403))
    clock.return_value += 61
    loaded_catalog.side_effect = BedrockDiscoveryError("ThrottlingException")
    # Patch the backend, not the `cache` proxy: pytest 9.2's monkeypatch
    # deletes on undo when the target's __dict__ lacks the name, and the
    # proxy's never has it, so teardown would delete `add` twice.
    backend = caches["default"]
    add = backend.add

    def another_worker_finishes(*args, **kwargs):
        monkeypatch.setattr(backend, "add", add)
        with pytest.raises(BedrockDiscoveryError, match="ThrottlingException"):
            bedrock_model_target(model="auto/anthropic.haiku")
        return False

    monkeypatch.setattr(backend, "add", another_worker_finishes)
    with pytest.raises(BedrockDiscoveryError, match="ThrottlingException"):
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
    loaded_catalog, clock, status, discoveries
):
    bedrock_model_target(model="auto/anthropic.haiku")
    loaded_catalog.return_value = replace(
        loaded_catalog.return_value,
        authorized_model_ids=frozenset({OLD_MODEL}),
    )
    for _ in range(2):
        bedrock_catalog_invalidate_on_error(
            SimpleNamespace(status_code=status)
        )
        assert bedrock_model_target(
            model="auto/anthropic.haiku"
        ).model.endswith(NEW_MODEL)
    loaded_catalog.assert_called_once()
    clock.return_value += 61
    target = bedrock_model_target(model="auto/anthropic.haiku")
    assert target.model.endswith(OLD_MODEL if discoveries == 2 else NEW_MODEL)
    assert loaded_catalog.call_count == discoveries


@pytest.mark.parametrize("warm", [False, True])
def test_concurrent_requests_share_a_refresh(loaded_catalog, clock, warm):
    if warm:
        bedrock_model_target(model="auto/anthropic.haiku")
        clock.return_value += 60 * 60 - 10
    started, release = Event(), Event()
    snapshot = loaded_catalog.return_value

    def discover(*args):
        started.set()
        assert release.wait(timeout=5)
        return snapshot

    loaded_catalog.side_effect = discover
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(bedrock_model_target, model="auto/anthropic.haiku")
        try:
            assert started.wait(timeout=5)
            if warm:
                assert bedrock_model_target(
                    model="auto/anthropic.haiku"
                ).model.endswith(NEW_MODEL)
                clock.return_value += 11
            with pytest.raises(BedrockModelUnavailable, match="in progress"):
                bedrock_model_target(model="auto/anthropic.haiku")
        finally:
            release.set()
        assert first.result().model.endswith(NEW_MODEL)
    assert loaded_catalog.call_count == (2 if warm else 1)


def test_invalidation_during_refresh_is_not_lost(loaded_catalog, clock):
    bedrock_model_target(model="auto/anthropic.haiku")
    error = SimpleNamespace(status_code=403)
    bedrock_catalog_invalidate_on_error(error)
    clock.return_value += 61

    def discover(*args):
        bedrock_catalog_invalidate_on_error(error)
        return loaded_catalog.return_value

    loaded_catalog.side_effect = discover
    bedrock_model_target(model="auto/anthropic.haiku")
    loaded_catalog.side_effect = None
    clock.return_value += 61
    bedrock_model_target(model="auto/anthropic.haiku")
    assert loaded_catalog.call_count == 3


@pytest.mark.parametrize(
    "inference_type, mantle",
    [
        ("ON_DEMAND", False),
        ("INFERENCE_PROFILE", False),
        ("INFERENCE_PROFILE", True),
    ],
)
def test_resolved_gpt_routes_apply_small_task_effort(inference_type, mantle):
    model_id = "openai.gpt-5.6-terra"
    native = FoundationModel.model_validate(
        _native_payload(model_id, inference_type=inference_type)
    )
    snapshot = BedrockCatalog(
        (native,),
        (MantleModel(id=model_id, created=native.released),) if mantle else (),
        (InferenceProfile.model_validate(_profile_payload(model_id)),),
        authorized_model_ids=frozenset({model_id}),
    )
    target = resolve_catalog(
        snapshot, BedrockPolicy("us-east-1"), "auto/openai.terra"
    )
    assert (
        target.invocation_options(small_task=True)["reasoning_effort"] == "low"
    )
    assert "reasoning_effort" not in target.invocation_options()


@pytest.mark.parametrize(
    "billing_model, provider",
    [
        (OLD_MODEL, "bedrock"),
        (f"bedrock_mantle/{GPT_MODEL}", "bedrock_mantle"),
    ],
)
def test_pricing_prefers_exact_regional_rates(billing_model, provider):
    import litellm

    region = "us-gov-west-1"
    regional = (
        f"{provider}/{region}/{billing_model.removeprefix('bedrock_mantle/')}"
    )
    target = ResolvedBedrockModel(
        billing_model, region, billing_model=billing_model
    )
    with patch.dict(
        litellm.model_cost, {billing_model: {}, regional: {}}, clear=True
    ):
        assert target.pricing_model() == regional


def test_commercial_pricing_alias_is_not_used_in_govcloud():
    import litellm

    target = ResolvedBedrockModel(
        GPT_MODEL, "us-east-1", billing_model=GPT_MODEL
    )
    with patch.dict(litellm.model_cost, {f"us.{GPT_MODEL}": {}}, clear=True):
        assert target.pricing_model() == f"us.{GPT_MODEL}"
        assert (
            replace(target, region="us-gov-west-1").pricing_model()
            == GPT_MODEL
        )


@pytest.mark.parametrize("content", [" Partial answer ", ""])
def test_reader_marks_limited_output_as_incomplete(
    reader_tool, completion, caplog, content
):
    choice = completion.return_value.choices[0]
    choice.message.content, choice.finish_reason = content, "length"
    tool, _ = reader_tool
    output = tool(thread_id="test")
    assert "incomplete" in output.result.lower()
    assert content.strip() in output.result
    assert output.render_data["response"] == output.result
    assert output.cost == 0.001
    assert "Document reader output truncated" in caplog.text
    assert completion.call_args.kwargs["max_tokens"] == 4096
    assert completion.call_args.kwargs["reasoning_effort"] == "low"
    completion.assert_called_once()


def test_model_choices_reuse_the_supplied_catalog(catalog, loaded_catalog):
    assert bedrock_model_choices(role="assistant", catalog=catalog) == (
        ("auto/anthropic.haiku", "Claude Haiku 5.5 (Economy)"),
    )
    assert bedrock_model_choices(catalog=BedrockCatalog((), (), ())) == ()
    loaded_catalog.assert_not_called()


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
        small_task_effort="low",
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
    "content_type, part_type, expected, effort",
    [
        ("text/plain", "text", "openai.gpt-5.6-terra", "low"),
        ("image/png", "image_url", "openai.gpt-5.6-terra", "low"),
        ("application/pdf", "file", NEW_MODEL, None),
    ],
)
def test_document_reader_uses_the_resolved_route_and_required_capabilities(
    reader_tool,
    upload,
    completion,
    content_type,
    part_type,
    expected,
    effort,
):
    upload.content_type = content_type
    completion.return_value.choices[0].message.content = " Answer "
    tool, uploads = reader_tool
    output = tool(thread_id="test")
    uploads.assert_called_once_with(
        id=str(upload.id), identity=upload.identity
    )
    args = completion.call_args.kwargs
    assert args["model"].endswith(expected)
    assert args["aws_region_name"] == "us-east-1"
    assert args["messages"][1]["content"][-1]["type"] == part_type
    assert args.get("reasoning_effort") == effort
    assert cache.get(SITE_CACHE_KEY).assistant_model == "auto/openai.terra"
    assert output.result == output.render_data["response"] == "Answer"
    assert output.cost == 0.001
