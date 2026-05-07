"""Django system checks for the chat app.

Run at startup (``manage.py check`` or any management command) and surface
configuration drift loudly — a fail here means the deploy doesn't proceed.

Currently checks:

- Every ``chat/prompts/courts/<slug>/court.json`` parses and conforms to
  ``chat/prompts/courts/_schema.json``. Catches typos, missing required
  fields, or schema drift introduced when adding a new partner court.
"""

import json
from pathlib import Path

import jsonschema
from django.core.checks import Error, Tags, register

_COURTS_DIR = Path(__file__).resolve().parent / "prompts" / "courts"
_SCHEMA_PATH = _COURTS_DIR / "_schema.json"


@register(Tags.compatibility)
def check_court_json_schema(app_configs, **kwargs):
    """Validate every court.json under chat/prompts/courts/ against the schema."""
    errors: list[Error] = []

    if not _SCHEMA_PATH.is_file():
        return [
            Error(
                f"Court schema missing at {_SCHEMA_PATH}",
                hint="Restore chat/prompts/courts/_schema.json.",
                id="chat.E001",
            )
        ]

    try:
        schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [
            Error(
                f"Court schema at {_SCHEMA_PATH} is invalid JSON: {exc}",
                id="chat.E002",
            )
        ]

    validator = jsonschema.Draft202012Validator(schema)

    for path in sorted(_COURTS_DIR.iterdir()):
        if not path.is_dir():
            continue
        meta_path = path / "court.json"
        if not meta_path.is_file():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(
                Error(
                    f"{meta_path}: invalid JSON ({exc})",
                    obj=str(meta_path),
                    id="chat.E003",
                )
            )
            continue
        for err in validator.iter_errors(meta):
            location = "/".join(str(p) for p in err.absolute_path) or "<root>"
            errors.append(
                Error(
                    f"{meta_path}: {err.message} (at {location})",
                    obj=str(meta_path),
                    id="chat.E004",
                )
            )

    return errors
