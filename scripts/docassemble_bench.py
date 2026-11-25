"""Drive the local docassemble bench from the command line (#1197).

    uv run python scripts/docassemble_bench.py sync           # upload new or changed files
    uv run python scripts/docassemble_bench.py sync -a        # upload everything
    uv run python scripts/docassemble_bench.py sync -n        # show what would upload
    uv run python scripts/docassemble_bench.py fill fc-eviction           # every persona
    uv run python scripts/docassemble_bench.py fill fc-eviction emily     # one persona

``sync`` uploads each folder under ``docassemble/`` to its own Playground
project (nd-name-change -> ndnamechange): ``*.yml`` to the interview editor,
``*.pdf`` to templates, ``*.css``/``*.svg`` to static. A file uploads when the
bench doesn't have it (a first run, or a reset with ``down -v``) or when it
changed since its last upload. Those hashes live in
``~/.cache/lp-docassemble-bench.json``, per bench URL.

``fill`` runs each test persona in the folder's ``personas.yml`` through its
interview without a browser: it starts a session, answers each screen in turn,
and downloads the document from the final screen's link. It writes to
``build/bench/<project>/``:

- ``<persona>.pdf``: the filled form, exactly as a litigant downloads it
- ``<persona>-outlined.pdf``: the same, with every field boxed and named
  (red for text, blue for checkboxes), to check placement by eye
- ``<persona>-outlined-<page>.png``: the outlined pages as images, when
  poppler's ``pdftoppm`` is installed

If a persona leaves a question unanswered, the interview stops there and
``fill`` names the screen and the variables it still wants.

The bench and its API key come from the repo's ``.env``: ``DA_ADMIN_API_KEY``
(or ``DOCASSEMBLE_API_KEY``, the same key under LP's name), and
``DOCASSEMBLE_PUBLIC_URL`` (default ``http://localhost:8100``). Setup:
``docs/docassemble.md``.
"""

import argparse
import hashlib
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from pathlib import Path

import yaml
from pypdf import PageObject, PdfReader, PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

REPO = Path(__file__).resolve().parents[1]
INTERVIEWS = REPO / "docassemble"
TARGETS = INTERVIEWS / "targets.yml"
OUTPUT = REPO / "build/bench"
STATE = Path.home() / ".cache/lp-docassemble-bench.json"
PLAYGROUND_FOLDERS = {
    ".yml": "questions",
    ".pdf": "templates",
    ".css": "static",
    ".svg": "static",
}
PERSONAS_FILE = "personas.yml"


# Configuration


def _env():
    """The repo's .env as a dict. Only the two bench values are read."""
    values = {}
    path = REPO / ".env"
    if path.exists():
        for line in path.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                name, _, value = line.partition("=")
                values[name.strip()] = value.strip().strip("\"'")
    return values


def _api_key(env) -> str:
    """The bench admin's key, or the one LP's prefill uses: on a local bench
    they're the same key under two names."""
    key = env.get("DA_ADMIN_API_KEY") or env.get("DOCASSEMBLE_API_KEY")
    if not key:
        sys.exit("Neither DA_ADMIN_API_KEY nor DOCASSEMBLE_API_KEY is in .env")
    return key


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Surface a redirect as an error instead of following it: urllib follows
    a POST's redirect as a GET without the body."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECTS = urllib.request.build_opener(_RefuseRedirects)

# Longest wait for one answer from docassemble, in seconds.
REQUEST_TIMEOUT = 120


class BenchUnreachable(SystemExit):
    """docassemble didn't answer at all. Exits like any other failure, unless
    a caller expects the outage, as an install's restart does."""


class Bench:
    """The docassemble API, authenticated with the admin key."""

    def __init__(self, target="bench"):
        self.base, self.key = _target(_env(), target)
        user = self.get_json("/api/user")
        self.user_id = user["id"]

    def _request(
        self,
        method,
        path,
        *,
        query=None,
        data=None,
        headers=None,
        timeout=REQUEST_TIMEOUT,
    ):
        url = f"{self.base}{path}"
        if query:
            url += "?" + urllib.parse.urlencode(query)
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"X-API-Key": self.key, **(headers or {})},
        )
        try:
            with _NO_REDIRECTS.open(request, timeout=timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            if 300 <= error.code < 400:
                # A redirect would turn a POST into a GET and drop the body.
                sys.exit(
                    f"{method} {url} was redirected (HTTP {error.code}) to "
                    f"{error.headers.get('Location')}"
                )
            return error.code, error.read()
        except (OSError, http.client.HTTPException) as error:
            # URLError (an OSError) covers a failed connect. A connection
            # dropped while reading the response, as during docassemble's
            # restart, raises RemoteDisconnected, ConnectionResetError or
            # TimeoutError instead, which urllib passes through unwrapped.
            reason = getattr(error, "reason", error)
            raise BenchUnreachable(
                f"Can't reach docassemble at {self.base}: {reason}"
            ) from error

    def get_json(self, path, **query):
        status, body = self._request("GET", path, query=query)
        if status != 200:
            sys.exit(f"GET {path}: HTTP {status}: {body.decode()[:500]}")
        return json.loads(body)

    def get_bytes(self, path, **query):
        status, body = self._request("GET", path, query=query)
        if status != 200:
            sys.exit(f"GET {path}: HTTP {status}: {body.decode()[:500]}")
        return body

    def post_json(self, path, payload):
        return self._request(
            "POST",
            path,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )

    def post_form(self, path, fields, files=()):
        """A multipart POST: ``fields`` as text, ``files`` as paths."""
        boundary = uuid.uuid4().hex
        parts = []
        for name, value in fields.items():
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
                f"\r\n\r\n{value}\r\n".encode()
            )
        for name, file_path in files:
            parts.append(
                f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; '
                f'filename="{file_path.name}"\r\nContent-Type: application/octet-stream'
                "\r\n\r\n".encode()
                + file_path.read_bytes()
                + b"\r\n"
            )
        parts.append(f"--{boundary}--\r\n".encode())
        return self._request(
            "POST",
            path,
            data=b"".join(parts),
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}"
            },
        )

    def interview(self, project, file_name):
        return f"docassemble.playground{self.user_id}{project}:{file_name}"


def _project(folder: Path):
    return folder.name.replace("-", "")


def _folder(name):
    folder = INTERVIEWS / name
    if not folder.is_dir():
        known = ", ".join(
            sorted(p.name for p in INTERVIEWS.iterdir() if p.is_dir())
        )
        sys.exit(f"No interview folder {name!r}. Known: {known}")
    return folder


# sync


def _selected(paths):
    """{interview folder: [files]} for the paths given, or every folder."""
    targets = [Path(p).resolve() for p in paths] or sorted(
        p for p in INTERVIEWS.iterdir() if p.is_dir()
    )
    selected = {}
    for target in targets:
        if not target.is_relative_to(INTERVIEWS):
            sys.exit(f"{target} is not under {INTERVIEWS}")
        if not target.exists():
            sys.exit(f"No interview folder or file {str(target)!r}")
        folder = target if target.is_dir() else target.parent
        files = sorted(folder.iterdir()) if target.is_dir() else [target]
        selected.setdefault(folder, []).extend(f for f in files if _ships(f))
    return selected


def _ships(file: Path) -> bool:
    """Whether a file in an interview folder goes to docassemble: the
    interviews, PDFs and branding, not the test personas or the README."""
    return file.suffix in PLAYGROUND_FOLDERS and file.name != PERSONAS_FILE


def _remote_names(bench, project, folder):
    """File names the bench holds in one Playground folder of a project."""
    status, body = bench._request(
        "GET", "/api/playground", query={"folder": folder, "project": project}
    )
    if status != 200:
        return set()
    return {
        item["filename"] if isinstance(item, dict) else item
        for item in json.loads(body or b"[]")
    }


def sync(args):
    bench = Bench()
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    uploaded = state.setdefault(bench.base, {})

    for folder, files in _selected(args.paths).items():
        project = _project(folder)
        print(f"== {project}")
        if not args.dry_run:
            bench.post_form("/api/playground/project", {"project": project})
        remote = {
            f: _remote_names(bench, project, f)
            for f in set(PLAYGROUND_FOLDERS.values())
        }
        for file in files:
            da_folder = PLAYGROUND_FOLDERS[file.suffix]
            rel = str(file.relative_to(REPO))
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            missing = file.name not in remote[da_folder]
            if not (args.all or missing or uploaded.get(rel) != digest):
                continue
            reason = "all" if args.all else "new" if missing else "changed"
            if args.dry_run:
                print(
                    f"   would upload  {da_folder:<9}  {file.name}  ({reason})"
                )
                continue
            status, body = bench.post_form(
                "/api/playground",
                {"project": project, "folder": da_folder},
                files=[("files", file)],
            )
            # Any non-success; a redirect has already exited in _request.
            if not 200 <= status < 300:
                sys.exit(
                    f"   FAILED  {da_folder}  {file.name}  (HTTP {status}): "
                    f"{body.decode()[:300]}"
                )
            uploaded[rel] = digest
            print(f"   uploaded  {da_folder:<9}  {file.name}  ({reason})")
        for interview in sorted(f for f in files if f.suffix == ".yml"):
            print(
                f"   run: {bench.base}/interview?i="
                f"{bench.interview(project, interview.name)}"
            )

    if not args.dry_run:
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(state, indent=2))


# package


def _pyproject(name: str, version: str) -> str:
    # The build settings docassemble's own Package button writes
    # (make_package_dir in docassemble/webapp/files/savedfile.py).
    return (
        "[build-system]\n"
        'requires = ["setuptools>=80.9.0"]\n'
        'build-backend = "setuptools.build_meta"\n'
        "\n"
        "[project]\n"
        f'name = "{name}"\n'
        f'version = "{version}"\n'
        "\n"
        "[tool.setuptools.packages.find]\n"
        'where = ["."]\n'
    )


def _package(folder: Path, version: str, out_dir: Path) -> Path:
    """An installable zip of one interview folder, in the layout docassemble's
    Package button produces: interviews under data/questions, PDFs under
    data/templates, CSS and SVG under data/static. ``docassemble`` is a
    namespace package shared with the server, so it gets no __init__.py;
    MANIFEST.in's graft is what carries the data files into the install."""
    project = _project(folder)
    root = f"docassemble-{project}"
    package = f"{root}/docassemble/{project}"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{root}.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            f"{root}/pyproject.toml",
            _pyproject(f"docassemble.{project}", version),
        )
        zf.writestr(
            f"{root}/MANIFEST.in", f"graft docassemble/{project}/data\n"
        )
        zf.writestr(f"{package}/__init__.py", f"__version__ = {version!r}\n")
        for file in sorted(folder.iterdir()):
            if _ships(file):
                data = PLAYGROUND_FOLDERS[file.suffix]
                zf.write(file, f"{package}/data/{data}/{file.name}")
    return path


# deploy


INSTALL_TIMEOUT = 15 * 60
INSTALL_POLL = 5


ADMIN_KEY_NAME = "DA_ADMIN_API_KEY"


def _aws_secret(secret_id, region, *, run=subprocess.run):
    """One AWS Secrets Manager secret's JSON, read with the aws CLI and
    whatever AWS identity the caller already has (a CI role, an SSO login)."""
    result = run(
        [
            "aws",
            "secretsmanager",
            "get-secret-value",
            "--secret-id",
            secret_id,
            "--region",
            region,
            "--query",
            "SecretString",
            "--output",
            "text",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        sys.exit(f"Can't read {secret_id}: {result.stderr.strip()}")
    return json.loads(result.stdout)


def _target(
    env,
    name,
    *,
    targets_file=TARGETS,
    environ=os.environ,
    read_secret=_aws_secret,
):
    """(base URL, admin API key) for a docassemble instance.

    ``bench`` is the local bench, set up from the repo's .env. Any other name
    is an instance in docassemble/targets.yml, which holds its URL and the
    AWS secret its admin key lives in. Nobody handles the key: it's read from
    that secret at deploy time, or taken from DA_API_KEY when set."""
    if name == "bench":
        base = env.get("DOCASSEMBLE_PUBLIC_URL") or "http://localhost:8100"
        return base.rstrip("/"), _api_key(env)
    targets = yaml.safe_load(targets_file.read_text()) or {}
    if name not in targets:
        known = ", ".join(["bench", *sorted(targets)])
        sys.exit(f"No target {name!r} in {targets_file.name}. Known: {known}")
    target = targets[name]
    base = target["url"].rstrip("/")
    if environ.get("DA_API_KEY"):
        return base, environ["DA_API_KEY"]
    if "secret" not in target:
        sys.exit(f"{name} names no AWS secret; set DA_API_KEY to deploy to it")
    secret = read_secret(target["secret"], target["region"])
    if ADMIN_KEY_NAME not in secret:
        held = ", ".join(sorted(secret)) or "nothing"
        sys.exit(
            f"{target['secret']} has no {ADMIN_KEY_NAME}; it holds {held}"
        )
    return base, secret[ADMIN_KEY_NAME]


def _install(bench, zip_path):
    """Upload a package zip for docassemble to install; returns its task id."""
    status, body = bench.post_form(
        "/api/package", {}, files=[("zip", zip_path)]
    )
    if not 200 <= status < 300:
        sys.exit(f"Install refused (HTTP {status}): {body.decode()[:500]}")
    return json.loads(body)["task_id"]


def _await_install(
    bench,
    task_id,
    *,
    timeout=INSTALL_TIMEOUT,
    interval=INSTALL_POLL,
    sleep=time.sleep,
    clock=time.monotonic,
):
    """Poll an install until docassemble reports it done, and return its log.

    docassemble restarts itself after installing, so the server going away or
    the ingress answering 5xx means keep waiting, not failure. `timeout` is
    elapsed time, including time spent waiting on slow answers."""
    deadline = clock() + timeout
    while (remaining := deadline - clock()) > 0:
        try:
            status, body = bench._request(
                "GET",
                "/api/package_update_status",
                query={"task_id": task_id},
                timeout=min(REQUEST_TIMEOUT, remaining),
            )
        except BenchUnreachable:
            status, body = None, b""
        if status == 200:
            result = json.loads(body)
            if result["status"] == "completed":
                if result.get("ok"):
                    return result.get("log", "")
                sys.exit(f"Install failed: {result.get('error_message')}")
            if result["status"] == "unknown":
                sys.exit(
                    "docassemble has no record of this install (status "
                    "unknown); check its Package Management page"
                )
        elif status is not None and status < 500:
            sys.exit(f"Install status: HTTP {status}: {body.decode()[:500]}")
        sleep(max(0, min(interval, deadline - clock())))
    sys.exit(f"Gave up after {timeout}s: docassemble is still installing")


def deploy(args):
    folder = _folder(args.folder)
    bench = Bench(args.target)
    version = time.strftime("1.0.%Y%m%d%H%M%S", time.gmtime())
    zip_path = _package(folder, version, OUTPUT / "packages")
    print(f"== docassemble.{_project(folder)} {version} -> {bench.base}")
    task_id = _install(bench, zip_path)
    print("   installing; docassemble restarts itself when it's done")
    # Success needs no log; a failure exits with docassemble's own message.
    _await_install(bench, task_id)
    print(f"   installed docassemble.{_project(folder)} {version}")


# fill


def _personas(folder):
    path = folder / PERSONAS_FILE
    if not path.exists():
        sys.exit(f"{path.relative_to(REPO)} doesn't exist")
    return yaml.safe_load(path.read_text())["personas"]


def _stopped_at(question):
    """A readable description of the screen an interview stopped on."""
    wanted = [
        field.get("variable_name")
        for field in question.get("fields", [])
        if field.get("variable_name")
    ]
    return f"{_question_text(question)!r} still wants: {', '.join(wanted) or '(no named fields)'}"


def _question_text(question):
    return re.sub(r"<[^>]+>", "", question.get("questionText", "")).strip()


MAX_SCREENS = 50


def _walk(bench, interview, name, answers):
    """Answer each screen from ``answers`` until one links a document.

    A ``mandatory`` question is asked until its own screen is answered, even
    when its variables are already set, so every screen is answered in turn,
    naming the question, the way docassemble's demo API client does.
    """
    session = bench.get_json("/api/session/new", i=interview)
    ids = {
        "i": interview,
        "session": session["session"],
        "secret": session.get("secret"),
    }
    question = bench.get_json("/api/session/question", **ids)
    answered = None
    for _ in range(MAX_SCREENS):
        file_number = _document_link(question)
        if file_number:
            return file_number
        wanted = [
            field["variable_name"]
            for field in question.get("fields", [])
            if field.get("variable_name")
        ]
        # The screen just answered, asking for the same variables again: a
        # field the persona left out (a show-if answer, an unset checkbox) is
        # still required. A list gather repeats a question with new variables.
        screen = (question.get("questionName"), wanted)
        if screen == answered:
            unanswered = [v for v in wanted if v not in answers]
            sys.exit(
                f"{name}: no answer for {', '.join(unanswered) or '(every field answered)'}. "
                f"docassemble asked {_question_text(question)!r} again"
            )
        answered = screen
        missing = [
            v
            for v in wanted
            if v not in answers and not _optional(question, v)
        ]
        if missing:
            sys.exit(
                f"{name}: no answer for {', '.join(missing)}. Stopped at {_stopped_at(question)}"
            )
        variables = {v: answers[v] for v in wanted if v in answers}
        if question.get("question_variable_name"):
            # A Continue-only screen: its own variable set to true moves on.
            variables[question["question_variable_name"]] = True
        if not variables:
            links = re.findall(r'href=\\?"([^"\\]+)', json.dumps(question))
            sys.exit(
                f"{name}: reached {_stopped_at(question)}, but found no document "
                f"link on it. Links seen: {links or 'none'}"
            )
        status, body = bench.post_json(
            "/api/session",
            {
                **ids,
                "question_name": question["questionName"],
                "variables": variables,
            },
        )
        if status != 200:
            sys.exit(
                f"{name}: answering failed (HTTP {status}): {body.decode()[:800]}"
            )
        question = json.loads(body)
    sys.exit(
        f"{name}: no document after {MAX_SCREENS} screens. Stopped at {_stopped_at(question)}"
    )


# docassemble's routes for a session's files (webapp/files/views.py), each
# carrying the file number the key-authenticated /api/file/<number> serves.
_FILE_ROUTES = re.compile(
    r"/(?:uploadedfile(?:download)?|storedfile(?:download)?/[^/]+)/(\d+)[/.]"
)


def _document_link(question):
    """The file number of the first document linked on a screen, if any."""
    match = _FILE_ROUTES.search(json.dumps(question))
    return match.group(1) if match else None


def _optional(question, variable):
    """Whether a field may go unanswered: not required, or hidden by a
    ``show if`` the persona's answers turn off (docassemble drops it)."""
    for field in question.get("fields", []):
        if field.get("variable_name") == variable:
            return not field.get("required", True) or bool(
                field.get("show_if_var") or field.get("show_if_js")
            )
    return False


def _fill_one(bench, folder, name, persona):
    project = _project(folder)
    interview = bench.interview(project, persona["interview"])
    file_number = _walk(bench, interview, name, persona["answers"])

    out = OUTPUT / project
    out.mkdir(parents=True, exist_ok=True)
    pdf = out / f"{name}.pdf"
    pdf.write_bytes(bench.get_bytes(f"/api/file/{file_number}"))
    outlined = _outline(pdf)
    images = _render(outlined)
    print(f"   {name}: {pdf.relative_to(REPO)}")
    print(f"   {' ' * len(name)}  {outlined.relative_to(REPO)}")
    for image in images:
        print(f"   {' ' * len(name)}  {image.relative_to(REPO)}")


def _pdf_text(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _outline(pdf: Path) -> Path:
    """A copy of ``pdf`` with each form field boxed and labeled with its name."""
    writer = PdfWriter(clone_from=PdfReader(pdf))
    for page in writer.pages:
        ops = []
        for annotation in page.get("/Annots") or []:
            widget = annotation.get_object()
            if widget.get("/Subtype") != "/Widget" or "/Rect" not in widget:
                continue
            x0, y0, x1, y1 = (float(v) for v in widget["/Rect"])
            name = str(
                widget.get("/T") or widget.get("/Parent", {}).get("/T", "")
            )
            color = "0 0 1" if widget.get("/FT") == "/Btn" else "1 0 0"
            ops += [
                f"q {color} RG {color} rg 0.6 w",
                f"{x0} {y0} {x1 - x0} {y1 - y0} re S",
                f"BT /BenchLabel 4.5 Tf {x0} {y1 + 1} Td ({_pdf_text(name)}) Tj ET Q",
            ]
        if not ops:
            continue
        # Draw on a blank page of the same size, then stack it on top:
        # merge_page keeps the form's own content and merges the resources.
        overlay = PageObject.create_blank_page(
            width=page.mediabox.width, height=page.mediabox.height
        )
        stream = DecodedStreamObject()
        stream.set_data("\n".join(ops).encode())
        overlay[NameObject("/Contents")] = writer._add_object(stream)
        overlay[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/BenchLabel"): DictionaryObject(
                            {
                                NameObject("/Type"): NameObject("/Font"),
                                NameObject("/Subtype"): NameObject("/Type1"),
                                NameObject("/BaseFont"): NameObject(
                                    "/Helvetica"
                                ),
                            }
                        )
                    }
                )
            }
        )
        page.merge_page(overlay)
    out = pdf.with_name(f"{pdf.stem}-outlined.pdf")
    writer.write(out)
    return out


def _render(pdf: Path):
    """PNGs of ``pdf``'s pages, if poppler's pdftoppm is installed."""
    for old in pdf.parent.glob(f"{pdf.stem}-*.png"):
        old.unlink()
    if not shutil.which("pdftoppm"):
        return []
    result = subprocess.run(
        ["pdftoppm", "-png", "-r", "110", str(pdf), str(pdf.with_suffix(""))],
        capture_output=True,
        text=True,
        check=True,
    )
    # Poppler has no Zapf Dingbats, the font checkbox marks are drawn in, and
    # says so once per checkbox. It still draws the marks, so one line says
    # that; anything else it reports is passed through.
    other = [
        line
        for line in result.stderr.splitlines()
        if line.strip()
        and "ZaDb" not in line
        and "ontconfig" not in line
        and "cache" not in line
    ]
    if "ZaDb" in result.stderr:
        print(
            "   (pdftoppm lacks the checkbox font; check marks render small)"
        )
    for line in other:
        print(f"   pdftoppm: {line}")
    return sorted(pdf.parent.glob(f"{pdf.stem}-*.png"))


def fill(args):
    bench = Bench()
    folder = _folder(args.folder)
    personas = _personas(folder)
    names = args.personas or list(personas)
    unknown = [n for n in names if n not in personas]
    if unknown:
        sys.exit(f"Unknown persona(s) {unknown}. Known: {', '.join(personas)}")
    print(f"== {_project(folder)}")
    for name in names:
        _fill_one(bench, folder, name, personas[name])


def main():
    parser = argparse.ArgumentParser(
        description="Drive the local docassemble bench: sync interviews, fill them with test personas."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    sync_parser = commands.add_parser(
        "sync", help="Upload interviews to the Playground."
    )
    sync_parser.add_argument(
        "paths", nargs="*", help="interview folders or files (default: all)"
    )
    sync_parser.add_argument(
        "-a", "--all", action="store_true", help="upload even if unchanged"
    )
    sync_parser.add_argument(
        "-n", "--dry-run", action="store_true", help="show what would upload"
    )
    sync_parser.set_defaults(run=sync)

    fill_parser = commands.add_parser(
        "fill", help="Fill an interview with test personas."
    )
    fill_parser.add_argument(
        "folder", help="interview folder under docassemble/, like fc-eviction"
    )
    fill_parser.add_argument(
        "personas", nargs="*", help="persona names (default: all)"
    )
    fill_parser.set_defaults(run=fill)

    deploy_parser = commands.add_parser(
        "deploy", help="Install an interview folder as a package."
    )
    deploy_parser.add_argument(
        "folder", help="interview folder under docassemble/, like fc-eviction"
    )
    deploy_parser.add_argument(
        "-t",
        "--target",
        default="bench",
        help="instance to install on: bench (default), or a name in "
        "docassemble/targets.yml, like qa",
    )
    deploy_parser.set_defaults(run=deploy)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
