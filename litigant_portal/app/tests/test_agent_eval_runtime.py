"""
Offline regression tests for eval capture and runtime judge diagnostics.
"""

import asyncio
import hashlib
import json
import shutil
from copy import deepcopy
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytest.importorskip("scripts.agent_eval.schema")

from scripts.agent_eval import report, runner, systems  # noqa: E402
from scripts.agent_eval.provider import Observer, usage_cost  # noqa: E402
from scripts.agent_eval.schema import (  # noqa: E402
    Config,
    GradingConfig,
    fingerprint,
    read_cases,
    verify_references,
    write_json,
)

MODEL_ID = "openai.gpt-99-luna"
BILLING_MODEL = f"bedrock_mantle/{MODEL_ID}"
INVOCATION_MODEL = f"bedrock/converse/us-east-1/us.{MODEL_ID}"


def test_model_discovery_freezes_versions_and_keeps_evaluator_pinned(
    monkeypatch,
):
    from litigant_portal.agents import bedrock
    from scripts.agent_eval import models

    native = tuple(
        bedrock.FoundationModel.model_validate(
            {
                "modelId": f"openai.gpt-{version}-luna",
                "inputModalities": ["TEXT"],
                "outputModalities": ["TEXT"],
                "inferenceTypesSupported": ["ON_DEMAND"],
                "responseStreamingSupported": True,
                "modelLifecycle": {
                    "status": "ACTIVE",
                    "startOfLifeTime": f"2026-01-0{day}T00:00:00Z",
                },
            }
        )
        for day, version in enumerate((98, 99), 1)
    )
    catalog = bedrock.BedrockCatalog(
        native,
        (),
        (),
        authorized_model_ids=frozenset(m.model_id for m in native),
    )
    discovery = Mock(return_value=catalog)
    monkeypatch.setattr(bedrock, "discover_catalog", discovery)
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    config = Config(models=["auto/openai.luna"])
    resolved = models.resolve_models(config)
    assert resolved["models"][config.models[0]]["model"].endswith(MODEL_ID)
    assert resolved["judges"][config.judges[0]]["model"].endswith(MODEL_ID)
    discovery.assert_called_once()
    pinned = models.evaluator_options(config.evaluator_model)
    assert pinned["model"] == config.evaluator_model
    assert (
        pinned["api_base"]
        == "https://bedrock-mantle.us-east-1.api.aws/openai/v1"
    )
    with pytest.raises(bedrock.BedrockModelUnavailable):
        models.resolve_models(Config(models=["auto/openai.terra"]))


def test_pinned_evaluator_is_independent_of_application_curation(monkeypatch):
    from litigant_portal.agents import bedrock
    from scripts.agent_eval import models

    saved = Config().model_dump()
    monkeypatch.delitem(bedrock.MODEL_MAPPING, "auto/openai.sol")
    monkeypatch.setitem(bedrock.MODEL_CHOICES, "best", [])

    config = Config()
    grading = GradingConfig.from_saved(saved)
    assert models.evaluator_options(grading.evaluator_model) == {
        "model": config.evaluator_model,
        "api_base": "https://bedrock-mantle.us-east-1.api.aws/openai/v1",
        "aws_region_name": "us-east-1",
    }


def test_frozen_corpus_matches_provenance():
    references = runner.HERE / "references"
    provenance = json.loads((references / "provenance.json").read_text())
    corpus = references / "corpus"
    assert {
        str(path.relative_to(corpus)): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in corpus.rglob("*")
        if path.is_file() and path.name != ".DS_Store"
    } == provenance["sha256"]


@pytest.mark.parametrize("variant", ["current", "chickens-a", "chickens-b"])
def test_frozen_corpus_load_ignores_application_files(
    tmp_path, monkeypatch, variant
):
    from litigant_portal.app.selectors import corpus
    from scripts.agent_eval.corpus import fixture_root

    for name in ("VARIABLES_PATH", "FORMS_DIR", "COURTS_DIR"):
        monkeypatch.setattr(corpus, name, tmp_path / "missing")
    root = runner.HERE / "references" / "corpus"
    if variant != "current":
        for folder in ("references", "fixtures"):
            shutil.copytree(
                runner.HERE / folder, tmp_path / "references" / folder
            )
        root = fixture_root(tmp_path, variant)
    loaded = corpus.corpus_load(root=root)
    assert set(loaded.courts) == {
        "north-dakota" if variant == "current" else "eval-ohio"
    }
    assert len(loaded.flows) == (2 if variant == "current" else 1)
    assert len(loaded.forms) == (8 if variant == "current" else 0)
    assert len(loaded.variables) == 34


def test_run_freezes_binary_references_and_rejects_changes(
    tmp_path, monkeypatch
):
    inputs = tmp_path / "inputs"
    for folder in ("references", "fixtures"):
        shutil.copytree(runner.HERE / folder, inputs / folder)
    shutil.copyfile(runner.HERE / "rubric.md", inputs / "rubric.md")
    asset = inputs / "references" / "asset.pdf"
    asset.write_bytes(b"%PDF-1.7\n%\xff\n")
    (asset.parent / ".DS_Store").write_bytes(b"Finder metadata")
    monkeypatch.setattr(runner, "HERE", inputs)
    monkeypatch.setattr(
        runner.importlib.metadata, "version", lambda name: "test"
    )

    run, _ = runner.make_run(Config(cases=["nd-fee"]), tmp_path / "runs")
    manifest = json.loads((run / "manifest.json").read_text())
    assert "references/.DS_Store" not in manifest["reference_hashes"]
    saved = run / "references" / "references" / asset.name
    assert saved.read_bytes() == asset.read_bytes()
    asset.write_bytes(b"Changed source")
    verify_references(run, manifest)

    (saved.parent / ".DS_Store").write_bytes(b"Updated Finder metadata")
    (run / "references" / ".DS_Store").write_bytes(b"New Finder metadata")
    verify_references(run, manifest)

    for name in ("extra.yml", ".unexpected"):
        extra = run / "references" / name
        extra.write_text("unexpected: content\n")
        with pytest.raises(
            ValueError, match="Saved reference files changed: "
        ) as error:
            verify_references(run, manifest)
        assert name in str(error.value)
        extra.unlink()
    saved.write_bytes(b"Changed snapshot")
    with pytest.raises(ValueError, match="Saved reference changed"):
        verify_references(run, manifest)

    saved.unlink()
    with pytest.raises(
        ValueError, match="Saved reference files changed: "
    ) as error:
        verify_references(run, manifest)
    assert "references/asset.pdf" in str(error.value)


def test_previously_hashed_finder_metadata_remains_verified(tmp_path):
    references = tmp_path / "references"
    references.mkdir()
    metadata = references / ".DS_Store"
    metadata.write_bytes(b"Recorded Finder metadata")
    hashes = {metadata.name: hashlib.sha256(metadata.read_bytes()).hexdigest()}
    definition = {"cases": [], "references": hashes, "scoring_version": "2"}
    manifest = {
        "schema_version": 3,
        "cases": [],
        "scoring_version": "2",
        "reference_hashes": hashes,
        "benchmark_id": fingerprint(definition),
    }
    verify_references(tmp_path, manifest)
    metadata.write_bytes(b"Changed Finder metadata")
    with pytest.raises(ValueError, match="Saved reference changed"):
        verify_references(tmp_path, manifest)
    metadata.unlink()
    with pytest.raises(ValueError, match="Saved reference files changed"):
        verify_references(tmp_path, manifest)


@pytest.mark.parametrize("during_migration", [True, False])
def test_eval_database_removed_after_failure(tmp_path, during_migration):
    from scripts.agent_eval import corpus

    name = "agent_eval_" + "a" * 32
    write_json(tmp_path / "manifest.json", {"evaluation_database": name})
    connection = MagicMock(settings_dict={"NAME": name})
    cursor = connection._nodb_cursor.return_value.__enter__.return_value
    with (
        patch("django.db.connection", connection),
        patch("django.db.connections.close_all") as close,
        patch(
            "django.core.management.call_command",
            side_effect=RuntimeError("interrupted")
            if during_migration
            else None,
        ),
        patch("litigant_portal.app.models.Site.objects.update"),
        pytest.raises(RuntimeError, match="interrupted"),
        corpus.corpus_session(tmp_path),
    ):
        raise RuntimeError("interrupted")
    assert [
        call.args[0].as_string() for call in cursor.execute.call_args_list
    ] == [
        f'CREATE DATABASE "{name}"',
        f'DROP DATABASE "{name}" WITH (FORCE)',
    ]
    close.assert_called_once()
    assert json.loads((tmp_path / "database.json").read_text())["removed"]


def test_legacy_fixture_restore_keeps_raw_site_values(tmp_path):
    from contextlib import nullcontext

    from scripts.agent_eval import corpus

    original = {field: f"original-{field}" for field in corpus.SITE_FIELDS}
    original["fast_model"] = "auto/openai.luna"
    write_json(
        tmp_path / "fixture-state.json", {"site": original, "restored": False}
    )
    with (
        patch.object(corpus, "fixture_lock", return_value=nullcontext()),
        patch("litigant_portal.app.models.Site.objects.update") as update,
        patch("litigant_portal.app.models.TopicFlow.objects.filter"),
    ):
        corpus.restore(tmp_path)
        update.assert_called_once_with(**original)
        assert json.loads((tmp_path / "fixture-state.json").read_text())[
            "restored"
        ]


@pytest.mark.parametrize("asynchronous", [False, True])
@pytest.mark.parametrize("stage", ["request", "stream"])
@pytest.mark.parametrize("category", [None, "timeout", "provider_error"])
def test_observer_captures_failures_without_changing_calls(
    asynchronous, stage, category
):
    error = (
        TimeoutError("synthetic timeout")
        if category == "timeout"
        else RuntimeError("synthetic provider failure")
    )
    chunk = {
        "choices": [],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2},
    }

    def chunks():
        yield chunk
        if category and stage == "stream":
            raise error

    async def async_chunks():
        for item in chunks():
            yield item

    original = AsyncMock() if asynchronous else Mock()
    if category and stage == "request":
        original.side_effect = error
    else:
        original.return_value = async_chunks() if asynchronous else chunks()
    calls, flushed = [], []
    config = Config(
        prices={
            "synthetic": {
                "input_per_million": 1,
                "output_per_million": 1,
                "source": "test",
            }
        }
    )
    kwargs = {
        "model": "synthetic",
        "stream": True,
        "timeout": 45,
        "num_retries": 0,
    }
    observed = []

    async def consume():
        import litellm

        if asynchronous:
            stream = await litellm.aresponses(**kwargs)
            async for item in stream:
                observed.append(item)
        else:
            observed.extend(litellm.completion(**kwargs))

    api = "aresponses" if asynchronous else "completion"
    with (
        patch(f"litellm.{api}", original),
        Observer(calls, config, lambda: flushed.append(deepcopy(calls))),
    ):
        if category:
            with pytest.raises(type(error)) as caught:
                asyncio.run(consume())
            assert caught.value is error
            assert flushed[-1][0]["error_category"] == category
        else:
            asyncio.run(consume())
    original.assert_called_once_with(**kwargs)
    assert len(calls) == 1
    assert calls[0]["request"]["timeout"] == 45
    assert calls[0]["request"]["num_retries"] == 0
    assert calls[0]["error_category"] == category
    if not category or stage == "stream":
        assert observed == [chunk]
        assert calls[0]["usage"] == chunk["usage"]
        assert calls[0]["cost_usd"] == pytest.approx(0.000012)
    if not category:
        assert "error" not in calls[0]


def test_observer_records_unset_options_without_passing_them():
    import litellm

    calls = []
    with (
        patch.object(litellm, "completion", return_value={}) as original,
        Observer(calls, Config()),
    ):
        litellm.completion(model="synthetic")
    original.assert_called_once_with(model="synthetic")
    assert calls[0]["request"]["timeout"] is None
    assert calls[0]["request"]["num_retries"] is None
    assert calls[0]["cost_usd"] is None


def test_observer_uses_shared_bedrock_pricing():
    import litellm

    model = f"bedrock_mantle/us-east-1/{MODEL_ID}"
    response = {"usage": {"prompt_tokens": 2, "completion_tokens": 3}}
    rates = {
        "litellm_provider": "bedrock_mantle",
        "input_cost_per_token": 1,
        "output_cost_per_token": 2,
    }
    calls = []
    with (
        patch.dict(litellm.model_cost, {BILLING_MODEL: rates}, clear=True),
        patch.object(litellm, "completion", return_value=response) as original,
        Observer(calls, Config()),
    ):
        assert litellm.completion(model=model) is response
    original.assert_called_once_with(model=model)
    call = calls[0]
    assert call["model"] == call["request"]["model"] == model
    assert call["cost_usd"] == 8
    assert call["pricing"]["model"] == BILLING_MODEL
    assert call["pricing"]["rates"]["input_cost_per_token"] == 1


@pytest.mark.parametrize(
    "prices, expected",
    [
        ({BILLING_MODEL: 1}, 1),
        ({BILLING_MODEL: 1, INVOCATION_MODEL: 2}, 2),
        ({"bedrock_mantle/openai.gpt-100-luna": 1}, None),
        ({f"bedrock_mantle/us-gov-west-1/{MODEL_ID}": 1}, None),
        ({BILLING_MODEL: 1, f"us.{MODEL_ID}": 2}, None),
    ],
)
def test_bedrock_price_overrides(prices, expected):
    import litellm

    config = Config(
        prices={
            model: {
                "input_per_million": rate,
                "output_per_million": 0,
                "source": "test",
            }
            for model, rate in prices.items()
        }
    )
    with patch.dict(litellm.model_cost, {}, clear=True):
        result = usage_cost(
            {"usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0}},
            INVOCATION_MODEL,
            config,
        )
    assert result["cost_usd"] == expected


@pytest.mark.parametrize("field", ["message", "error"])
@pytest.mark.parametrize("system", ["no_judge", "current"])
def test_current_adapter_preserves_stream_error_and_export(field, system):
    case = read_cases(Config())[0].model_copy(update={"history": []})
    export = {"messages": []}
    error = {"type": "error", field: "Continue with the guided flow."}
    response = MagicMock()
    response.__iter__.return_value = iter(
        "data: " + json.dumps(event) + "\n\n"
        for event in (
            {"type": "thread", "thread_id": "test"},
            error,
            {"type": "done"},
        )
    )
    events = []
    with (
        patch(
            "litigant_portal.app.services.chat_engine.chat_stream",
            return_value=response,
        ),
        patch("litigant_portal.app.models.ChatThread.objects.get"),
        patch(
            "litigant_portal.app.selectors.chat_engine.chat_thread_export_data",
            return_value=export,
        ),
        pytest.raises(RuntimeError, match="Continue with the guided flow"),
    ):
        systems.invoke(system, case, "synthetic", Mock(), events.append)
    response.close.assert_called_once()
    assert error in events
    assert events[-1] == {"type": "thread_export", "data": export}


def write_run(path, rows, system="current"):
    case = read_cases(Config())[0].model_dump()
    manifest = {
        "config": Config(
            systems=[system],
            models=["auto/openai.luna"],
            repetitions=len(rows),
        ).model_dump(),
        "resolved_models": {
            "models": {"auto/openai.luna": {"model": "synthetic"}},
            "judges": {"auto/openai.luna": {"model": "synthetic-judge"}},
        },
        "cases": [case],
        "reference_hashes": {},
        "scoring_version": runner.SCORING_VERSION,
        "planned_attempts": len(rows),
        "identity_id": "test",
        "attempts": [],
    }
    manifest["benchmark_id"] = fingerprint(
        {key: manifest[key] for key in ("cases", "scoring_version")}
        | {"references": {}}
    )
    for index, row in enumerate(rows):
        name = f"attempt-{index}.json"
        record = {
            "system": system,
            "model": "auto/openai.luna",
            "model_id": "synthetic",
            "judge": "auto/openai.luna"
            if system in {"current", "old"}
            else None,
            "case": case,
            "repeat": index + 1,
            "status": "completed",
            "answer": "Answer",
            "calls": [],
            "events": [],
            "first_text_seconds": None,
        } | row
        write_json(path / name, record)
        manifest["attempts"].append(name)
    write_json(path / "manifest.json", manifest)
    return path / manifest["attempts"][0]


def test_run_and_report_keep_model_judge_pairs_separate(tmp_path):
    from scripts.agent_eval.remote import ContainerWorker

    config = Config(
        judges=["auto/openai.luna", "auto/openai.sol"],
        cases=["nd-fee"],
        repetitions=1,
    )
    resolved = {
        field: {model: {"model": f"resolved-{model}"} for model in values}
        for field, values in (
            ("models", config.models),
            ("judges", config.judges),
        )
    }

    def finish(run, path, timeout):
        row = json.loads(path.read_text())
        cost = 2 if row["judge"] == "auto/openai.sol" else 1
        row.update(status="error", calls=[{"cost_usd": cost}])
        write_json(path, row)

    def request(command, **kwargs):
        if command == "attempt":
            run = next(tmp_path.iterdir())
            finish(run, run / kwargs["path"], config.timeout_seconds)
        return {}

    remote = MagicMock(spec=ContainerWorker)
    remote.__enter__.return_value = remote
    remote.request.side_effect = request
    with (
        patch(
            "scripts.agent_eval.remote.ContainerWorker", return_value=remote
        ),
        patch.object(runner.models, "resolve_models", return_value=resolved),
        patch.object(runner, "execute_worker", side_effect=finish),
        patch.object(
            runner.importlib.metadata, "version", return_value="test"
        ),
    ):
        run = runner.run_suite(config, tmp_path)
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["planned_attempts"] == len(set(manifest["attempts"])) == 8
    assert manifest["resolved_models"] == resolved
    result = report.summarize(run)
    assert len(result["systems"]) == 8
    for row in result["systems"]:
        assert row["planned"] == row["recorded"] == 1
        assert row["mean_cost_usd"] == (
            2 if row["judge"] == "auto/openai.sol" else 1
        )
        assert row["model_ids"] == [f"resolved-{row['model']}"]


def test_legacy_grading_keeps_evaluator_and_original_artifacts(tmp_path):
    from scripts.agent_eval.schema import GradingConfig

    target = write_run(tmp_path, [{}], system="old")
    manifest_path = tmp_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    config = manifest["config"]
    del config["evaluator_model"], config["judges"]
    config.update(
        systems=["old"],
        models=["luna"],
        judge_model="sol",
        model_ids={
            "luna": BILLING_MODEL,
            "sol": "bedrock_mantle/openai.gpt-5.6-sol",
        },
    )
    write_json(manifest_path, manifest)
    candidate = json.loads(target.read_text())
    candidate.pop("judge")
    candidate["model"] = "luna"
    write_json(target, candidate)
    batch = tmp_path / "judgments" / "batch"
    write_json(
        batch / "batch.json",
        {
            "config": config,
            "status": "incomplete",
            "judgments": {target.name: "grade.json"},
        },
    )
    write_json(batch / "grade.json", {"status": "error", "calls": []})
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    assert (
        GradingConfig.from_saved(config).evaluator_model
        == config["model_ids"]["sol"]
    )
    runner.recover_run(tmp_path, dry_run=True)
    runner.judge_run(tmp_path, retry_failed=True, dry_run=True)
    with pytest.raises(ValueError, match="same evaluator"):
        runner.judge_run(
            tmp_path, Config().evaluator_model, retry_failed=True, dry_run=True
        )
    result = report.summarize(tmp_path)
    assert result["evaluator_model"] == config["model_ids"]["sol"]
    assert result["systems"][0]["judge"] is None
    assert result["systems"][0]["runtime_judge_models"] == ["unknown"]
    assert all(
        path.read_bytes() == content for path, content in before.items()
    )


@pytest.mark.parametrize("system", ["standalone", "new"])
def test_report_rejects_retired_systems(tmp_path, system):
    write_run(tmp_path, [{}])
    path = tmp_path / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["config"]["systems"] = [system]
    write_json(path, manifest)
    with pytest.raises(ValueError, match="Unsupported evaluation system"):
        report.summarize(tmp_path)


@pytest.mark.parametrize("system", ["raw", "no_judge", "current"])
def test_failed_attempt_sets_and_retains_judge_configuration(tmp_path, system):
    from litigant_portal.app.cache import SITE_CACHE_KEY

    target = write_run(tmp_path, [{}], system=system)
    judge_model = "synthetic-judge" if system == "current" else None

    def commit(callback):
        update.assert_called_once_with(judge_model=judge_model)
        invalidate.assert_not_called()
        callback()

    def fail(*args, **kwargs):
        assert kwargs["invocation_options"] == {"model": "synthetic"}
        assert (
            json.loads(target.read_text()).get("runtime_judge_model")
            == judge_model
        )
        if system == "raw":
            update.assert_not_called()
            invalidate.assert_not_called()
        else:
            update.assert_called_once_with(judge_model=judge_model)
            invalidate.assert_called_once_with(SITE_CACHE_KEY)
        raise RuntimeError("synthetic generation failure")

    with (
        patch.object(runner.corpus, "setup_django"),
        patch("litigant_portal.app.models.UserIdentity.objects.get"),
        patch("litigant_portal.app.models.Site.objects.update") as update,
        patch("django.core.cache.cache.delete") as invalidate,
        patch(
            "django.db.transaction.on_commit", side_effect=commit
        ) as on_commit,
        patch.object(runner.systems, "invoke", side_effect=fail),
    ):
        runner.worker(tmp_path, target, grading=False)
    if system == "raw":
        on_commit.assert_not_called()
    else:
        on_commit.assert_called_once()
    row = json.loads(target.read_text())
    assert row["status"] == "error"
    assert row.get("runtime_judge_model") == judge_model
    assert "synthetic generation failure" in row["error"]


def test_attempt_deadline_is_distinct_from_provider_timeout(tmp_path):
    target = write_run(tmp_path, [{"status": "running"}])
    process = MagicMock()
    process.poll.return_value = None
    process.pid = 123
    clock = iter([0, 301])
    with (
        patch.object(runner.subprocess, "Popen", return_value=process),
        patch.object(runner.os, "killpg") as kill,
        patch.object(
            runner.time, "monotonic", side_effect=lambda: next(clock, 302)
        ),
    ):
        runner.execute_worker(tmp_path, target, 300)
    row = json.loads(target.read_text())
    assert row["status"] == "error"
    assert row["error_category"] == "attempt_timeout"
    kill.assert_called_once_with(123, runner.signal.SIGKILL)


@pytest.mark.parametrize("system", ["current", "no_judge", "old"])
def test_report_separates_generation_deadlines_and_judging(tmp_path, system):
    generation = {
        "request": {"stream": True, "timeout": 45, "num_retries": 0},
        "error_category": "timeout",
        "cost_usd": 0.1,
    }
    audits = {
        "messages": [
            {
                "data": {
                    "kind": "judge",
                    "verdict": {"approved": False, "findings": []},
                }
            },
            {
                "data": {
                    "kind": "judge",
                    "verdict": {"approved": True, "findings": []},
                }
            },
            {
                "data": {
                    "kind": "judge",
                    "error": "judge_failed",
                    "error_category": "timeout",
                }
            },
            {"data": {"kind": "title", "error": "timeout"}},
        ]
    }
    write_run(
        tmp_path,
        [
            {
                "status": "error",
                "error_category": "RuntimeError",
                "runtime_judge_model": "synthetic-judge",
                "calls": [generation],
                "events": [{"type": "thread_export", "data": audits}],
            },
            {"status": "error", "error_category": "attempt_timeout"},
            {
                "runtime_judge_model": None,
                "detail": {"thread_export": {"messages": []}},
                "calls": [
                    {
                        "request": {
                            "stream": True,
                            "timeout": None,
                            "num_retries": None,
                        },
                        "error_category": None,
                        "cost_usd": 0.2,
                    }
                ],
            },
            {"calls": [{"request": {"stream": True}, "cost_usd": None}]},
        ],
        system=system,
    )
    folder = tmp_path / "judgments" / "batch"
    write_json(
        folder / "batch.json",
        {
            "status": "incomplete",
            "judgments": {"attempt-2.json": "grade.json"},
        },
    )
    write_json(
        folder / "grade.json",
        {"status": "error", "error_category": "invalid_json", "calls": []},
    )
    before = {path: path.read_bytes() for path in tmp_path.rglob("*.json")}
    result = report.summarize(tmp_path)
    first, deadline, disabled, legacy = result["attempts"]
    assert first["generation_timeout"] is True
    assert first["generation_settings"] == [{"timeout": 45, "num_retries": 0}]
    assert first["runtime_judge_outcomes"] == {
        "approved": 1,
        "rejected": 1,
        "timeout": 1,
    }
    assert deadline["attempt_timeout"] is True
    assert disabled["runtime_judge_model"] is None
    assert disabled["generation_settings"] == [
        {"timeout": "provider_default", "num_retries": "provider_default"}
    ]
    assert disabled["runtime_judge_outcomes"] == {}
    assert legacy["generation_settings"] == [
        {"timeout": "unknown", "num_retries": "unknown"}
    ]
    assert legacy["generation_timeout"] is None
    assert legacy["runtime_judge_model"] == "unknown"
    assert legacy["runtime_judge_outcomes"] is None
    summary = result["systems"][0]
    assert summary["generation_timeout_attempts"] == 1
    assert summary["attempt_timeouts"] == 1
    assert summary["runtime_judge_outcomes"] == first["runtime_judge_outcomes"]
    assert summary["execution_failures"] == 2
    assert summary["known_cost_usd"] == pytest.approx(0.3)
    assert first["overall"] == 0
    assert result["grading"]["errors"] == {"ungraded": 3, "invalid_json": 1}
    assert all(
        path.read_bytes() == content for path, content in before.items()
    )
