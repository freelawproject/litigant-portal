#!/usr/bin/env python3
"""Build a prefilled GitHub issue-form URL from a self-describing content blob.

Workaround for `gh issue create` not posting to YAML issue *forms*
non-interactively (it only fills the legacy free-text body). This reads a
content blob, maps it onto the right form's fields via URL query params, prints
the URL, and tries to open it in a browser. Retire once `gh` supports forms.

## Content format

The blob declares its own type and title in a small header, then one section
per form field, keyed by the field's `id` from the template YAML in
`.github/ISSUE_TEMPLATE/`:

    type: task
    title: Tighten the corpus loader error messages

    [what]
    CorpusValidationError should list every bad id-ref at once, not just the
    first.

    [why]
    Authors fix one error, re-run, hit the next. Slow feedback loop.

    [dod]
    - [ ] All cross-ref failures aggregate into one error

- `type:` selects the template. Accepted: task, bug (bug-report),
  enhancement (enh/feature), qa (qa-round).
- `title:` is the issue title.
- `[field-id]` starts a section; its body runs until the next `[field-id]`
  or end of input. Field ids must match the template (e.g. task → what / why
  / dod; enhancement → problem / proposal). Unknown ids are sent anyway —
  GitHub ignores params it doesn't recognize, so the cost of a typo is a
  blank field, not an error.

The label (`bug`, `task`, …) is applied automatically by the template itself.

## Usage

    python3 scripts/file_issue.py < issue.md      # read stdin
    python3 scripts/file_issue.py issue.md         # read a file
    make file-issue < issue.md                     # via make
    make file-issue FILE=issue.md

Repo is detected from `git remote get-url origin`; override with --repo.
Use --print-only to skip the browser-open attempt (it always prints the URL).
"""

import argparse
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

# type marker (and aliases) → template filename in .github/ISSUE_TEMPLATE/
_TEMPLATES = {
    "task": "task.yml",
    "bug": "bug-report.yml",
    "bug-report": "bug-report.yml",
    "enhancement": "enhancement.yml",
    "enh": "enhancement.yml",
    "feature": "enhancement.yml",
    "qa": "qa-round.yml",
    "qa-round": "qa-round.yml",
}

_HEADER_RE = re.compile(r"^(type|title):\s*(.*)$", re.IGNORECASE)
_FIELD_RE = re.compile(r"^\[([a-z0-9_-]+)\]\s*$")

# `id:` of a body item in a GitHub issue-form template YAML.
_TEMPLATE_ID_RE = re.compile(r"^\s+id:\s*(\S+)\s*$", re.MULTILINE)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_TEMPLATE_DIR = _REPO_ROOT / ".github" / "ISSUE_TEMPLATE"


def _parse_blob(text):
    """Parse the content blob into (type, title, {field_id: body}).

    Header lines (`type:` / `title:`) are read until the first `[field]`
    marker; everything after is split into field sections.
    """
    issue_type = None
    title = None
    fields = {}
    current = None
    body_lines = []

    def _flush():
        if current is not None:
            fields[current] = "\n".join(body_lines).strip("\n")

    in_body = False
    for line in text.splitlines():
        field_match = _FIELD_RE.match(line)
        if field_match:
            _flush()
            current = field_match.group(1)
            body_lines = []
            in_body = True
            continue
        if not in_body:
            header = _HEADER_RE.match(line)
            if header:
                key, value = header.group(1).lower(), header.group(2).strip()
                if key == "type":
                    issue_type = value.lower()
                else:
                    title = value
                continue
            if not line.strip():
                continue  # blank lines in the header are noise
        body_lines.append(line)
    _flush()

    return issue_type, title, fields


def _template_field_ids(template):
    """Return the set of body-item ids declared in a template YAML.

    Read with a regex rather than a YAML parser to stay stdlib-only.
    Returns None if the template file can't be read, so validation can be
    skipped gracefully rather than blocking URL generation.
    """
    path = _TEMPLATE_DIR / template
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return {m.group(1) for m in _TEMPLATE_ID_RE.finditer(text)}


def _detect_repo():
    """Return owner/repo from the origin remote, or None."""
    try:
        url = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    # git@github.com:owner/repo.git  or  https://github.com/owner/repo.git
    match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", url)
    return match.group(1) if match else None


def _open_in_browser(url):
    """Best-effort browser open. Returns True on success, False otherwise."""
    opener = "open" if sys.platform == "darwin" else "xdg-open"
    try:
        subprocess.run(
            [opener, url],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def build_url(repo, template, title, fields):
    """Assemble the GitHub issue-form prefill URL."""
    params = {"template": template}
    if title:
        params["title"] = title
    params.update(fields)
    query = urllib.parse.urlencode(params)
    return f"https://github.com/{repo}/issues/new?{query}"


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a prefilled GitHub issue-form URL from a blob.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to a content blob. Omit to read from stdin.",
    )
    parser.add_argument(
        "-r",
        "--repo",
        help="owner/repo override (default: detect from origin remote).",
    )
    parser.add_argument(
        "-p",
        "--print-only",
        action="store_true",
        help="Print the URL but do not try to open a browser.",
    )
    args = parser.parse_args(argv)

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        text = sys.stdin.read()
    else:
        parser.error("no content: pass a file path or pipe a blob on stdin")

    issue_type, title, fields = _parse_blob(text)

    if not issue_type:
        parser.error("content is missing a `type:` line")
    template = _TEMPLATES.get(issue_type)
    if not template:
        valid = ", ".join(sorted(set(_TEMPLATES)))
        parser.error(f"unknown type {issue_type!r}. Expected one of: {valid}")
    if not title:
        parser.error("content is missing a `title:` line")

    valid_ids = _template_field_ids(template)
    if valid_ids is not None:
        unknown = [f for f in fields if f not in valid_ids]
        if unknown:
            print(
                f"warning: {issue_type} ({template}) has no field(s): "
                f"{', '.join(unknown)} — they will render blank. "
                f"Valid ids: {', '.join(sorted(valid_ids))}",
                file=sys.stderr,
            )

    repo = args.repo or _detect_repo()
    if not repo:
        parser.error("could not detect repo; pass --repo owner/repo")

    url = build_url(repo, template, title, fields)

    print(url)
    if not args.print_only:
        if _open_in_browser(url):
            print(
                "\nOpened in your browser. Set the assignee and submit.",
                file=sys.stderr,
            )
        else:
            print(
                "\nBrowser open unavailable here — click the URL above.",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
