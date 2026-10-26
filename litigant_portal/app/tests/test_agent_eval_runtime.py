"""
Offline regression tests for eval capture and runtime judge diagnostics.
"""

import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytest.importorskip("scripts.agent_eval.schema")

from scripts.agent_eval import report, runner, systems  # noqa: E402
from scripts.agent_eval.provider import Observer  # noqa: E402
from scripts.agent_eval.schema import (  # noqa: E402
    Config,
    fingerprint,
    read_cases,
    write_json,
)


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


@pytest.mark.parametrize("field", ["message", "error"])
def test_current_adapter_preserves_stream_error_and_export(field):
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
        systems.current(case, "synthetic", Mock(), events.append)
    response.close.assert_called_once()
    assert error in events
    assert events[-1] == {"type": "thread_export", "data": export}


def write_run(path, rows):
    case = read_cases(Config())[0].model_dump()
    manifest = {
        "config": Config(
            systems=["current"], models=["luna"], repetitions=len(rows)
        ).model_dump(),
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
            "system": "current",
            "model": "luna",
            "model_id": "synthetic",
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


@pytest.mark.parametrize("judge_model", [None, "synthetic-judge"])
def test_failed_attempt_retains_judge_configuration(tmp_path, judge_model):
    target = write_run(tmp_path, [{}])

    def fail(*args):
        assert (
            json.loads(target.read_text())["runtime_judge_model"]
            == judge_model
        )
        raise RuntimeError("synthetic generation failure")

    with (
        patch.object(runner.corpus, "setup_django"),
        patch("litigant_portal.app.models.UserIdentity.objects.get"),
        patch(
            "litigant_portal.app.selectors.site.site_get",
            return_value=SimpleNamespace(judge_model=judge_model),
        ),
        patch.object(runner.systems, "invoke", side_effect=fail),
    ):
        runner.worker(tmp_path, target, grading=False)
    row = json.loads(target.read_text())
    assert row["status"] == "error"
    assert row["runtime_judge_model"] == judge_model
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


def test_report_separates_generation_deadlines_and_judging(tmp_path):
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
