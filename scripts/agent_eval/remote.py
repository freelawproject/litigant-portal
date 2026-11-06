"""
Run application calls in an existing container without image or mount changes.
"""

import base64
import importlib.metadata
import json
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid
from contextlib import ExitStack, suppress
from pathlib import Path

from .provider import safe
from .schema import HERE, ROOT, Config, verify_references, write_json

# Only the standard library is needed until the uploaded worker is imported.
# Requests travel over stdin, never through interpolated shell commands.
BOOTSTRAP = """
import contextlib, json, pathlib, sys, tempfile
payload = json.loads(sys.stdin.readline())
wire = sys.stdout
with tempfile.TemporaryDirectory(prefix="agent-eval-") as directory:
    root = pathlib.Path(directory)
    package = root / "scripts" / "agent_eval"
    package.mkdir(parents=True)
    for name, content in payload.pop("code").items():
        (package / name).write_text(content)
    sys.path.insert(0, str(root))
    with contextlib.redirect_stdout(sys.stderr):
        from scripts.agent_eval.remote import serve
        serve(root / "run", payload, wire)
"""


class ContainerWorker:
    """
    Exchange commands and incremental artifacts with one disposable worker.
    """

    def __init__(self, run: Path):
        self.run = run
        self.process = None
        self.log = None
        self.messages = queue.Queue()
        self.closed = False

    def __enter__(self):
        manifest = json.loads((self.run / "manifest.json").read_text())
        self.timeout = manifest["config"]["timeout_seconds"]
        self.log = (self.run / "container.log").open("a")
        try:
            self.process = subprocess.Popen(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "django",
                    "python",
                    "-u",
                    "-c",
                    BOOTSTRAP,
                ],
                cwd=ROOT,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self.log,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
            threading.Thread(target=self._read, daemon=True).start()
            state = self.run / "fixture-state.json"
            self._send(
                {
                    "code": {
                        path.name: path.read_text()
                        for path in HERE.glob("*.py")
                    },
                    "manifest": manifest,
                    "references": {
                        name: base64.b64encode(
                            (self.run / "references" / name).read_bytes()
                        ).decode("ascii")
                        for name in manifest["reference_hashes"]
                    },
                    "recovery": json.loads(state.read_text())
                    if state.exists()
                    else None,
                }
            )
            ready = self._receive(time.monotonic() + 30)
            if ready["kind"] != "ready":
                raise RuntimeError("Container worker did not start.")
            return self
        except BaseException:
            self.__exit__(*sys.exc_info())
            raise

    def _read(self):
        try:
            for line in self.process.stdout:
                self.messages.put(json.loads(line))
        except (ValueError, OSError):
            self.messages.put(
                {
                    "kind": "error",
                    "message": "Invalid container worker response; see container.log.",
                }
            )
        finally:
            self.messages.put({"kind": "eof"})

    def _send(self, message):
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def _receive(self, deadline):
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError(
                    "Container worker did not respond before its deadline."
                )
            try:
                message = self.messages.get(timeout=min(0.25, remaining))
            except queue.Empty:
                continue
            if message["kind"] == "artifact":
                path = (self.run / message["path"]).resolve()
                if not path.is_relative_to(self.run.resolve()):
                    raise RuntimeError("Invalid artifact path from container.")
                path.parent.mkdir(parents=True, exist_ok=True)
                pending = path.with_suffix(".tmp")
                pending.write_text(message["text"])
                pending.replace(path)
                continue
            if message["kind"] == "eof":
                raise RuntimeError(
                    "Container worker disconnected; see container.log and the README cleanup instructions."
                )
            if message["kind"] == "error":
                raise RuntimeError(message["message"])
            return message

    def request(self, command, **values):
        self._send({"command": command, **values})
        deadline = time.monotonic() + (
            self.timeout + 30 if command in {"start", "attempt"} else 30
        )
        message = self._receive(deadline)
        if message["kind"] != "result":
            raise RuntimeError(
                "Container worker stopped before completing the command."
            )
        return message.get("value", {})

    def close(self):
        if self.process is None or self.closed:
            return
        try:
            # Interrupt any active child before deleting the database.
            with suppress(BrokenPipeError):
                self._send({"command": "close"})
                self.process.stdin.close()
            deadline = time.monotonic() + 15
            while True:
                message = self._receive(deadline)
                if message["kind"] == "closed":
                    self.closed = True
                    if message.get("error"):
                        raise RuntimeError(message["error"])
                    break
        finally:
            with suppress(BrokenPipeError):
                self.process.stdin.close()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # EOF tells the remote supervisor to reap its child and clean
                # up. Killing the local Docker client alone cannot do so.
                self.process.kill()
                self.process.wait()
            self.process.stdout.close()

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.close()
        except (OSError, RuntimeError) as failure:
            if exc_type is None:
                raise
            print(f"Container cleanup: {failure}", file=sys.stderr)
        finally:
            if self.log is not None:
                self.log.close()


def application_state() -> dict:
    from django.conf import settings

    from .runner import source_state

    root = Path(settings.BASE_DIR).parent
    source = source_state(root, application=True)
    source.update(
        python=sys.version,
        packages={
            name: importlib.metadata.version(name)
            for name in ("Django", "litellm", "pydantic", "PyYAML")
        },
    )
    return source


def serve(run: Path, payload: dict, wire):
    """
    Own the evaluation database and reap children on disconnect.
    """
    from . import corpus
    from .runner import execute_worker

    commands = queue.Queue()
    stopped = threading.Event()

    def send(value):
        try:
            wire.write(json.dumps(safe(value)) + "\n")
            wire.flush()
        except BrokenPipeError:
            stopped.set()

    def publish(path):
        if path.exists():
            send(
                {
                    "kind": "artifact",
                    "path": str(path.relative_to(run)),
                    "text": path.read_text(),
                }
            )

    def stop(*_):
        stopped.set()
        commands.put({"command": "close"})

    def read_commands():
        try:
            for line in sys.stdin:
                message = json.loads(line)
                if message["command"] == "close":
                    break
                commands.put(message)
        finally:
            stop()

    manifest = payload["manifest"]
    write_json(run / "manifest.json", manifest)
    for name, content in payload["references"].items():
        path = (run / "references" / name).resolve()
        if not path.is_relative_to((run / "references").resolve()):
            raise ValueError("Invalid reference path.")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(base64.b64decode(content, validate=True))
    verify_references(run, manifest)
    if payload["recovery"] is not None:
        write_json(run / "fixture-state.json", payload["recovery"])
    config = Config.model_validate(manifest["config"])
    stack, failure, started = ExitStack(), None, False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    threading.Thread(target=read_commands, daemon=True).start()
    try:
        corpus.setup_django(
            run if manifest.get("evaluation_database") else None
        )
        send({"kind": "ready"})
        while not stopped.is_set():
            message = commands.get()
            command = message["command"]
            if command == "close":
                break
            if command in {"fixture", "attempt"} and not started:
                raise ValueError("Start the evaluation database first.")
            value = {}
            if command == "start":
                from litigant_portal.app.models import UserIdentity

                if started or not manifest.get("evaluation_database"):
                    raise ValueError("A new evaluation database is required.")
                fast = (
                    config.model_ids[config.legacy_fast_model]
                    if config.legacy_fast_model
                    else None
                )
                stack.enter_context(
                    corpus.corpus_session(
                        run,
                        fast_model=fast,
                        notify=lambda: publish(run / "database.json"),
                    )
                )
                identity = UserIdentity.objects.create(
                    session_key=f"agent-eval-{uuid.uuid4().hex[:29]}"
                )
                manifest["identity_id"] = str(identity.pk)
                write_json(run / "manifest.json", manifest)
                write_json(run / "application.json", application_state())
                publish(run / "application.json")
                started = True
                value = {
                    "identity_id": str(identity.pk),
                    "application": "application.json",
                }
            elif command == "fixture":
                variant = message["variant"]
                if variant == "current":
                    root = run / "references" / "references" / "corpus"
                    corpus.install_fixture(root, "north-dakota")
                else:
                    root = corpus.fixture_root(run, variant)
                    corpus.install_fixture(root, "eval-ohio")
                    for path in sorted(root.rglob("*.yml")):
                        publish(path)
                path = run / "corpora" / f"{variant}-database.json"
                write_json(path, corpus.snapshot_current())
                publish(path)
            elif command == "attempt":
                path = run / message["path"]
                write_json(path, message["record"])
                execute_worker(
                    run,
                    path,
                    config.timeout_seconds,
                    publish=publish,
                    cancelled=stopped.is_set,
                )
            elif command == "restore":
                if manifest.get("evaluation_database"):
                    raise ValueError(
                        "Use the README disposable database cleanup instructions."
                    )
                corpus.restore(run)
                publish(run / "fixture-state.json")
            else:
                raise ValueError(f"Unknown worker command: {command}")
            send({"kind": "result", "value": value})
    except Exception as exc:
        failure = safe(f"{type(exc).__name__}: {exc}")[:2000]
        send({"kind": "error", "message": failure})
    finally:
        try:
            stack.close()
        except Exception as exc:
            failure = safe(f"Evaluation cleanup failed: {exc}")[:2000]
        send({"kind": "closed", "error": failure})
