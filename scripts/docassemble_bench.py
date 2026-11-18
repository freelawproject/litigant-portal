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
interview without a browser: it starts a session, sets every answer at once,
and downloads the document from the final screen's link. It writes to
``build/bench/<project>/``:

- ``<persona>.pdf``: the filled form, exactly as a litigant downloads it
- ``<persona>-outlined.pdf``: the same, with every field boxed and named
  (red for text, blue for checkboxes), to check placement by eye
- ``<persona>-outlined-<page>.png``: the outlined pages as images, when
  poppler's ``pdftoppm`` is installed

If a persona leaves a question unanswered, the interview stops there and
``fill`` names the screen and the variables it still wants.

The bench and its API key come from the repo's ``.env``: ``DA_ADMIN_API_KEY``,
and ``DOCASSEMBLE_PUBLIC_URL`` (default ``http://localhost:8100``). Setup:
``docs/docassemble.md``.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
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


class _RefuseRedirects(urllib.request.HTTPRedirectHandler):
    """Surface a redirect as an error instead of following it: urllib follows
    a POST's redirect as a GET without the body."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


_NO_REDIRECTS = urllib.request.build_opener(_RefuseRedirects)


class Bench:
    """The docassemble API, authenticated with the admin key."""

    def __init__(self):
        env = _env()
        self.base = (
            env.get("DOCASSEMBLE_PUBLIC_URL") or "http://localhost:8100"
        ).rstrip("/")
        key = env.get("DA_ADMIN_API_KEY")
        if not key:
            sys.exit("DA_ADMIN_API_KEY is missing from .env")
        self.key: str = key
        user = self.get_json("/api/user")
        self.user_id = user["id"]

    def _request(self, method, path, *, query=None, data=None, headers=None):
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
            with _NO_REDIRECTS.open(request, timeout=120) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            if 300 <= error.code < 400:
                # A redirect would turn a POST into a GET and drop the body.
                sys.exit(
                    f"{method} {url} was redirected (HTTP {error.code}) to "
                    f"{error.headers.get('Location')}"
                )
            return error.code, error.read()
        except urllib.error.URLError as error:
            sys.exit(f"Can't reach the bench at {self.base}: {error.reason}")

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
        known = ", ".join(sorted(p.name for p in INTERVIEWS.iterdir() if p.is_dir()))
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
        folder = target if target.is_dir() else target.parent
        files = sorted(folder.iterdir()) if target.is_dir() else [target]
        selected.setdefault(folder, []).extend(
            f
            for f in files
            if f.suffix in PLAYGROUND_FOLDERS and f.name != PERSONAS_FILE
        )
    return selected


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
                print(f"   would upload  {da_folder:<9}  {file.name}  ({reason})")
                continue
            status, body = bench.post_form(
                "/api/playground",
                {"project": project, "folder": da_folder},
                files=[("files", file)],
            )
            if not 200 <= status < 300:  # any non-success; redirects already exit
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
    text = re.sub(r"<[^>]+>", "", question.get("questionText", "")).strip()
    return f"{text!r} still wants: {', '.join(wanted) or '(no named fields)'}"


MAX_SCREENS = 50


def _walk(bench, interview, name, answers):
    """Answer each screen from ``answers`` until one links a document.

    A ``mandatory`` question is asked until its own screen is answered, even
    when its variables are already set, so every screen is answered in turn,
    naming the question, the way docassemble's demo API client does.
    """
    session = bench.get_json("/api/session/new", i=interview)
    ids = {"i": interview, "session": session["session"], "secret": session.get("secret")}
    question = bench.get_json("/api/session/question", **ids)
    for _ in range(MAX_SCREENS):
        file_number = _document_link(question)
        if file_number:
            return file_number
        wanted = [
            field["variable_name"]
            for field in question.get("fields", [])
            if field.get("variable_name")
        ]
        missing = [v for v in wanted if v not in answers and not _optional(question, v)]
        if missing:
            sys.exit(f"{name}: no answer for {', '.join(missing)}. Stopped at {_stopped_at(question)}")
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
            sys.exit(f"{name}: answering failed (HTTP {status}): {body.decode()[:800]}")
        question = json.loads(body)
    sys.exit(f"{name}: no document after {MAX_SCREENS} screens. Stopped at {_stopped_at(question)}")


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
            name = str(widget.get("/T") or widget.get("/Parent", {}).get("/T", ""))
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
                                NameObject("/BaseFont"): NameObject("/Helvetica"),
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
    if not shutil.which("pdftoppm"):
        return []
    for old in pdf.parent.glob(f"{pdf.stem}-*.png"):
        old.unlink()
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
        if line.strip() and "ZaDb" not in line and "ontconfig" not in line
        and "cache" not in line
    ]
    if "ZaDb" in result.stderr:
        print("   (pdftoppm lacks the checkbox font; check marks render small)")
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

    sync_parser = commands.add_parser("sync", help="Upload interviews to the Playground.")
    sync_parser.add_argument("paths", nargs="*", help="interview folders or files (default: all)")
    sync_parser.add_argument("-a", "--all", action="store_true", help="upload even if unchanged")
    sync_parser.add_argument("-n", "--dry-run", action="store_true", help="show what would upload")
    sync_parser.set_defaults(run=sync)

    fill_parser = commands.add_parser("fill", help="Fill an interview with test personas.")
    fill_parser.add_argument("folder", help="interview folder under docassemble/, like fc-eviction")
    fill_parser.add_argument("personas", nargs="*", help="persona names (default: all)")
    fill_parser.set_defaults(run=fill)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
