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
from collections import Counter
from contextlib import nullcontext, suppress
from datetime import UTC, datetime
from pathlib import Path

from . import corpus, judge, systems
from .provider import Observer, safe
from .schema import (
    HERE,
    ROOT,
    Case,
    CitedGrade,
    Config,
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
    write_json(
        references / "judge-schema.json", CitedGrade.model_json_schema()
    )
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
                protocol_path = judge.judgment_path(
                    run, run, record["judge_contract"]
                )
                protocol = json.loads(protocol_path.read_text())
                if fingerprint(protocol) != record["judge_contract_hash"]:
                    raise ValueError("Saved judge contract changed.")
                record["answer_passages"] = judge.answer_passages(
                    candidate["answer"]
                )
                flush()
                record.update(
                    asyncio.run(
                        judge.evaluate(
                            candidate, config, run, protocol, capture
                        )
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
            status="error",
            error=safe(f"{type(exc).__name__}: {exc}")[:2000],
            error_category=getattr(exc, "category", type(exc).__name__),
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


def latest_judgments(run: Path) -> tuple[Path | None, dict, dict[str, Path]]:
    paths = sorted((run / "judgments").glob("*/batch.json"))
    if not paths:
        return None, {}, {}
    path = paths[-1]
    batch = json.loads(path.read_text())
    return (
        path.parent,
        batch,
        {
            candidate: judge.judgment_path(run, path.parent, name)
            for candidate, name in batch["judgments"].items()
        },
    )


def new_batch(run: Path, config: Config, mode: str, source: Path | None):
    folder = run / "judgments" / f"{stamp()}-{uuid.uuid4().hex[:6]}"
    folder.mkdir(parents=True)
    write_json(folder / "source.json", source_state())
    batch = {
        "config": config.model_dump(),
        "judgments": {},
        "status": "running",
        "mode": mode,
        "source_batch": source.name if source else None,
    }
    # Publish the batch only once its carried-forward results are recorded.
    # An interrupted setup must not hide the previous batch's valid grades.
    return folder, batch


def finish_batch(folder: Path, batch: dict, *, interrupted=False):
    rows = [
        json.loads((folder / name).read_text())
        for name in batch["judgments"].values()
    ]
    counts = Counter(row["status"] for row in rows)
    errors = Counter(
        row.get("error_category", row.get("error", "Missing result"))
        for row in rows
        if row["status"] != "completed"
    )
    batch["counts"] = dict(counts)
    batch["errors"] = dict(errors)
    batch["status"] = (
        "interrupted"
        if interrupted
        else ("incomplete" if errors else "completed")
    )
    write_json(folder / "batch.json", batch)
    print(
        f"Judgments: {counts['completed']} accepted; {sum(errors.values())} unresolved.",
        flush=True,
    )
    for reason, count in errors.items():
        print(f"  {count}: {reason}", flush=True)


def recover_run(run: Path, *, dry_run=False) -> Path | None:
    """
    Revalidate saved responses and preserve original artifacts and paid calls.
    """
    run = run.resolve()
    manifest = json.loads((run / "manifest.json").read_text())
    verify_references(run, manifest)
    source, previous, paths = latest_judgments(run)
    if source is None:
        raise ValueError("There are no saved judgments to recover.")
    config = Config.model_validate(previous["config"])
    prepared = {}
    counts = Counter()
    for candidate_path in manifest["attempts"]:
        candidate = json.loads((run / candidate_path).read_text())
        if candidate["status"] != "completed":
            continue
        original = paths.get(candidate_path)
        row = (
            json.loads(original.read_text())
            if original
            else {
                "candidate": candidate_path,
                "status": "error",
                "calls": [],
                "config": config.model_dump(),
            }
        )
        try:
            if not row.get("raw_judge_text"):
                raise ValueError(
                    "No saved judge response; a judge call is needed."
                )
            if row.get("answer_passages") is not None and row[
                "answer_passages"
            ] != judge.answer_passages(candidate["answer"]):
                raise ValueError(
                    "Saved answer no longer matches the judged passages."
                )
            result = judge.parse_response(
                row["raw_judge_text"],
                candidate,
                config.weights,
                row.get("judge_format_version", 1),
            )
        except ValueError as exc:
            row = {
                **row,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "error_category": getattr(exc, "category", type(exc).__name__),
            }
            row.pop("grade", None)
            row.pop("score", None)
            counts["unresolved"] += 1
        else:
            if (
                row["status"] == "completed"
                and row["score"] == result["score"]
            ):
                counts["retained"] += 1
                prepared[candidate_path] = (original, None)
                continue
            row = {
                **row,
                **result,
                "status": "completed",
                "recovery": "offline",
            }
            row.pop("error", None)
            row.pop("error_category", None)
            counts["recovered"] += 1
        if original:
            origin, _ = judge.paid_calls(run, original)
            row.update(
                calls=[],
                calls_source=str(origin.relative_to(run)),
                recovered_from=str(original.relative_to(run)),
            )
        prepared[candidate_path] = (original, row)
    print(
        f"Recovery: {counts['retained']} retained; {counts['recovered']} recovered; "
        f"{counts['unresolved']} need judging. No API calls.",
        flush=True,
    )
    if dry_run:
        return None
    folder, batch = new_batch(run, config, "recover", source)
    batch["recovery_counts"] = dict(counts)
    for candidate_path, (original, row) in prepared.items():
        if row is None:
            target = original
        else:
            relative = Path(candidate_path)
            target = folder / f"{relative.parent.name}-{relative.stem}.json"
            write_json(target, row)
        batch["judgments"][candidate_path] = os.path.relpath(target, folder)
    finish_batch(folder, batch)
    return folder


def judge_run(
    run: Path, model: str | None = None, *, retry_failed=False, dry_run=False
) -> Path | None:
    run = run.resolve()
    manifest = json.loads((run / "manifest.json").read_text())
    verify_references(run, manifest)
    source, previous, paths = latest_judgments(run)
    config = Config.model_validate(
        previous["config"] if retry_failed and previous else manifest["config"]
    )
    if retry_failed and source is None:
        raise ValueError("There is no judgment batch to retry.")
    original_model = config.model_ids[config.judge_model]
    if model:
        config = Config.model_validate(
            {**config.model_dump(), "judge_model": model}
        )
    if retry_failed and config.model_ids[config.judge_model] != original_model:
        raise ValueError(
            "Retry must use the same judge model; use full judging to change models."
        )
    jobs, retained = [], {}
    for candidate_path in manifest["attempts"]:
        candidate = json.loads((run / candidate_path).read_text())
        if candidate["status"] != "completed":
            continue
        prior = paths.get(candidate_path)
        if (
            retry_failed
            and prior
            and json.loads(prior.read_text())["status"] == "completed"
        ):
            retained[candidate_path] = prior
        else:
            jobs.append((candidate_path, candidate))
    print(
        f"Judging plan: {len(jobs)} API calls; {len(retained)} judgments retained; "
        "0 candidate answers regenerated.",
        flush=True,
    )
    if dry_run or not jobs:
        return source
    if not os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "").strip():
        raise ValueError("Set AWS_BEARER_TOKEN_BEDROCK locally for judging.")
    folder, batch = new_batch(
        run, config, "retry_failed" if retry_failed else "judge", source
    )
    protocol = judge.contract(run)
    write_json(folder / "judge-contract.json", protocol)
    batch["judge_contract_hash"] = fingerprint(protocol)
    batch["planned_calls"] = len(jobs)
    batch["retained"] = len(retained)
    batch["judgments"] = {
        key: os.path.relpath(path, folder) for key, path in retained.items()
    }
    interrupted = True
    try:
        # Publish pending records before the first call, so retries of an
        # interrupted batch cannot accidentally omit its unstarted work.
        for candidate_path, _ in jobs:
            relative = Path(candidate_path)
            target = folder / f"{relative.parent.name}-{relative.stem}.json"
            write_json(
                target,
                {
                    "candidate": candidate_path,
                    "status": "running",
                    "calls": [],
                    "config": config.model_dump(),
                    "judge_format_version": judge.FORMAT_VERSION,
                    "judge_contract": str(
                        (folder / "judge-contract.json").relative_to(run)
                    ),
                    "judge_contract_hash": batch["judge_contract_hash"],
                    "replaces": str(paths[candidate_path].relative_to(run))
                    if candidate_path in paths
                    else None,
                },
            )
            batch["judgments"][candidate_path] = target.name
        write_json(folder / "batch.json", batch)
        for i, (candidate_path, _) in enumerate(jobs, 1):
            target = folder / batch["judgments"][candidate_path]
            print(f"Judging [{i}/{len(jobs)}] {candidate_path}", flush=True)
            execute_worker(run, target, config.timeout_seconds, grading=True)
            row = json.loads(target.read_text())
            print(
                f"  {row['status']}"
                + (f": {row['error']}" if row.get("error") else ""),
                flush=True,
            )
        interrupted = False
    finally:
        finish_batch(folder, batch, interrupted=interrupted)
    return folder
