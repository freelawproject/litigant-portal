"""
Persist a reproducible matrix and execute each attempt in a bounded process.
"""

import asyncio
import importlib.metadata
import itertools
import json
import os
import random
import shutil
import signal
import subprocess
import sys
import time
import uuid
from contextlib import nullcontext, suppress
from datetime import UTC, datetime
from pathlib import Path

from . import corpus, judge, systems
from .provider import Observer, safe
from .schema import (
    HERE,
    ROOT,
    Case,
    Config,
    Grade,
    fingerprint,
    read_cases,
    verify_references,
    write_json,
)

SCORING_VERSION = "1"


def stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def source_state(root: Path = ROOT, *, application=False) -> dict:
    files = {}
    folders = (
        ("lp_agent", "litigant_portal")
        if application
        else ("scripts/agent_eval",)
    )
    for folder in folders:
        for directory, dirs, names in os.walk(root / folder):
            dirs[:] = sorted(
                name
                for name in dirs
                if not name.startswith(".") and name != "__pycache__"
            )
            for name in sorted(names):
                path = Path(directory) / name
                if (
                    path.suffix in {".py", ".yml", ".yaml", ".md", ".toml"}
                    or name == "uv.lock"
                ):
                    files[str(path.relative_to(root))] = fingerprint(
                        path.read_text()
                    )
    if application:
        for name in ("pyproject.toml", "uv.lock", "tox.ini"):
            files[name] = fingerprint((root / name).read_text())
    revision = os.environ.get("EVAL_GIT_SHA") or os.environ.get(
        "GIT_SHA", "unknown"
    )
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    return {
        "kind": "application" if application else "evaluator",
        "git_revision": revision,
        "source_fingerprint": fingerprint(files),
        "files": files,
    }


def make_run(config: Config, output: Path) -> tuple[Path, list[Case]]:
    cases = read_cases(config)
    output.mkdir(parents=True, exist_ok=True)
    run = output / f"{stamp()}-{config.slug}"
    try:
        run.mkdir()
    except FileExistsError:
        run = output / f"{stamp()}-{config.slug}-{uuid.uuid4().hex[:6]}"
        run.mkdir()
    references = run / "references"
    references.mkdir()
    for folder in ("references", "fixtures"):
        shutil.copytree(HERE / folder, references / folder)
    shutil.copyfile(HERE / "rubric.md", references / "rubric.md")
    write_json(references / "judge-schema.json", Grade.model_json_schema())
    reference_hashes = {
        str(path.relative_to(references)): fingerprint(path.read_text())
        for path in sorted(references.rglob("*"))
        if path.is_file()
    }
    write_json(run / "source.json", source_state())
    manifest = {
        "schema_version": 1,
        "scoring_version": SCORING_VERSION,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "running",
        "config": config.model_dump(),
        "cases": [case.model_dump() for case in cases],
        "reference_hashes": reference_hashes,
        "benchmark_id": fingerprint(
            {
                "cases": [case.model_dump() for case in cases],
                "references": reference_hashes,
                "scoring_version": SCORING_VERSION,
            }
        ),
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("litellm", "pydantic", "PyYAML", "matplotlib")
        },
        "python": sys.version,
        "planned_attempts": len(cases)
        * len(config.systems)
        * len(config.models)
        * config.repetitions,
        "attempts": [],
    }
    write_json(run / "manifest.json", manifest)
    return run, cases


def execute_worker(
    run: Path,
    path: Path,
    timeout: float,
    grading=False,
    publish=lambda path: None,
    cancelled=lambda: False,
):
    """
    Bound the actual child process, including when running inside Docker.
    """
    args = [
        sys.executable,
        "-m",
        "scripts.agent_eval",
        "_worker",
        str(run),
        str(path),
    ]
    if grading:
        args.append("--grading")
    started = time.monotonic()
    failure, interrupted, last_mtime = None, False, None
    with path.with_suffix(".log").open("w") as log:
        process = subprocess.Popen(
            args,
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
        try:
            while process.poll() is None:
                if cancelled():
                    failure = "Interrupted by controller."
                    break
                if time.monotonic() - started >= timeout:
                    failure = f"Attempt exceeded {timeout:g} seconds."
                    break
                mtime = path.stat().st_mtime_ns
                if mtime != last_mtime:
                    publish(path)
                    last_mtime = mtime
                time.sleep(0.1)
            if failure is None and process.returncode:
                failure = "Worker exited without a terminal result."
        except KeyboardInterrupt:
            failure, interrupted = "Interrupted by user.", True
        finally:
            if process.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    row = json.loads(path.read_text())
    if failure or row["status"] == "running":
        row.update(
            status="interrupted" if interrupted or cancelled() else "error",
            error=failure or "Missing terminal result.",
        )
        row["elapsed_seconds"] = time.monotonic() - started
        write_json(path, row)
    publish(path)
    publish(path.with_suffix(".log"))
    if interrupted:
        raise KeyboardInterrupt


def worker(run: Path, path: Path, grading: bool):
    manifest = json.loads((run / "manifest.json").read_text())
    record = json.loads(path.read_text())
    config = Config.model_validate(record.get("config", manifest["config"]))
    started = time.monotonic()
    last_flush = 0.0

    def flush(force=True):
        nonlocal last_flush
        now = time.monotonic()
        record["elapsed_seconds"] = now - started
        if force or now - last_flush >= 0.25:
            write_json(path, record)
            last_flush = now

    def emit(event):
        if event["type"] == "text":
            if event["delta"] and record["first_text_seconds"] is None:
                record["first_text_seconds"] = time.monotonic() - started
            record["answer"] += event["delta"]
        else:
            record["events"].append(safe(event))
        flush(False)

    def capture(text):
        record["raw_judge_text"] = text
        flush()

    try:
        identity = None
        if not grading and record["system"] != "raw":
            corpus.setup_django()
            from litigant_portal.app.models import UserIdentity

            identity = UserIdentity.objects.get(pk=manifest["identity_id"])
        # Django startup and identity lookup are outside response latency.
        started = time.monotonic()
        flush()
        with Observer(record["calls"], config, flush):
            if grading:
                candidate = json.loads((run / record["candidate"]).read_text())
                record.update(
                    asyncio.run(
                        judge.evaluate(candidate, config, run, capture)
                    )
                )
            else:
                resource = record.get("resource_root")
                detail = systems.invoke(
                    record["system"],
                    Case.model_validate(record["case"]),
                    record["model_id"],
                    identity,
                    emit,
                    str(run / resource) if resource else None,
                )
                record["detail"] = safe(detail)
                if not record["answer"].strip():
                    raise RuntimeError("System produced no visible answer.")
                if record["system"] == "old" and any(
                    call.get("finish_reason")
                    not in {"stop", "tool_calls", "function_call"}
                    for call in record["calls"]
                    if call["request"].get("stream")
                ):
                    raise RuntimeError(
                        "Old model stream did not finish normally."
                    )
        record["status"] = "completed"
        if not grading and record["system"] == "old":
            record["auxiliary_failures"] = [
                {
                    key: call.get(key)
                    for key in ("model", "error", "error_message")
                }
                for call in record["calls"]
                if call.get("error") and not call["request"].get("stream")
            ]
    except Exception as exc:
        record.update(
            status="error", error=safe(f"{type(exc).__name__}: {exc}")[:2000]
        )
    finally:
        flush()


def run_suite(config: Config, output: Path) -> Path:
    from .remote import ContainerWorker

    run, cases = make_run(config, output)
    print(f"Results: {run}", flush=True)
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    needs_db = any(system != "raw" for system in config.systems)
    try:
        rng = random.Random(config.seed)
        with ContainerWorker(run) if needs_db else nullcontext() as remote:
            if remote:
                manifest.update(remote.request("start"))
                write_json(manifest_path, manifest)
            for variant in dict.fromkeys(case.fixture for case in cases):
                if remote:
                    remote.request("fixture", variant=variant)
                jobs = list(
                    itertools.product(
                        [case for case in cases if case.fixture == variant],
                        config.systems,
                        config.models,
                        range(1, config.repetitions + 1),
                    )
                )
                rng.shuffle(jobs)
                for case, system, model, repeat in jobs:
                    relative = (
                        Path(f"{system}-{model}") / f"{case.id}-r{repeat}.json"
                    )
                    row = {
                        "schema_version": 1,
                        "system": system,
                        "model": model,
                        "model_id": config.model_ids[model],
                        "case": case.model_dump(),
                        "repeat": repeat,
                        "status": "running",
                        "answer": "",
                        "first_text_seconds": None,
                        "events": [],
                        "calls": [],
                        "resource_root": f"corpora/{variant}"
                        if variant != "current" and system != "raw"
                        else None,
                    }
                    write_json(run / relative, row)
                    manifest["attempts"].append(str(relative))
                    write_json(manifest_path, manifest)
                    print(
                        f"[{len(manifest['attempts'])}/{manifest['planned_attempts']}] {relative}",
                        flush=True,
                    )
                    if system == "raw":
                        execute_worker(
                            run, run / relative, config.timeout_seconds
                        )
                    else:
                        remote.request(
                            "attempt", path=str(relative), record=row
                        )
                    completed = json.loads((run / relative).read_text())
                    warnings = len(completed.get("auxiliary_failures", []))
                    suffix = (
                        f" ({warnings} auxiliary call failures)"
                        if warnings
                        else ""
                    )
                    print(f"  {completed['status']}{suffix}", flush=True)
        manifest["status"] = "completed"
    except BaseException:
        manifest["status"] = "interrupted"
        raise
    finally:
        write_json(manifest_path, manifest)
    return run


def judge_run(run: Path, model: str | None = None) -> Path:
    manifest = json.loads((run / "manifest.json").read_text())
    verify_references(run, manifest)
    config = Config.model_validate(manifest["config"])
    if model:
        config = Config.model_validate(
            {**config.model_dump(), "judge_model": model}
        )
    folder = run / "judgments" / f"{stamp()}-{uuid.uuid4().hex[:6]}"
    folder.mkdir(parents=True)
    write_json(folder / "source.json", source_state())
    batch = {
        "config": config.model_dump(),
        "judgments": {},
        "status": "running",
    }
    try:
        for candidate_path in manifest["attempts"]:
            candidate = json.loads((run / candidate_path).read_text())
            if candidate["status"] != "completed":
                continue
            relative = Path(candidate_path)
            target = folder / f"{relative.parent.name}-{relative.stem}.json"
            write_json(
                target,
                {
                    "candidate": candidate_path,
                    "status": "running",
                    "calls": [],
                    "config": config.model_dump(),
                },
            )
            batch["judgments"][candidate_path] = target.name
            write_json(folder / "batch.json", batch)
            print(f"Judging {candidate_path}", flush=True)
            execute_worker(run, target, config.timeout_seconds, grading=True)
        batch["status"] = "completed"
    finally:
        write_json(folder / "batch.json", batch)
    return folder
