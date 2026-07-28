import yaml
from django.conf import settings

LIBRARY_DIR = settings.BASE_DIR / "library"

_COURTS_DIR = LIBRARY_DIR / "courts"


def _clean_rows(
    items, *, fields: tuple[str, ...], required: str
) -> list[dict]:
    """Normalize a YAML list into dict rows; drop rows missing ``required``."""
    rows = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        row = {field: str(item.get(field) or "").strip() for field in fields}
        if row[required]:
            rows.append(row)
    return rows


def court_library_list() -> list[dict]:
    """Court configs from ``library/courts/<slug>/config.yml`` for the
    admin library."""
    entries = []
    for path in sorted(_COURTS_DIR.glob("*/config.yml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(raw, dict):
            continue
        entries.append(
            {
                "slug": path.parent.name,
                "name": str(raw.get("name") or path.parent.name).strip(),
                "court_name": str(raw.get("court_name") or "").strip(),
                "jurisdiction_level": str(
                    raw.get("jurisdiction_level") or ""
                ).strip(),
                "state": str(raw.get("state") or "").strip().upper(),
                "official_url": str(raw.get("official_url") or "").strip(),
                "official_resources_url": str(
                    raw.get("official_resources_url") or ""
                ).strip(),
                "contacts": _clean_rows(
                    raw.get("contacts"),
                    fields=("name", "phone", "email", "url", "note"),
                    required="name",
                ),
                "resources": _clean_rows(
                    raw.get("resources"),
                    fields=("label", "url", "note"),
                    required="label",
                ),
            }
        )
    return entries


def court_library_get(*, slug: str) -> dict | None:
    """A single court config by slug, or ``None``."""
    return next((e for e in court_library_list() if e["slug"] == slug), None)


def _clean_field_rows(items) -> list[dict]:
    """Normalize a flow YAML's fields into rich TopicFlowField rows; drop
    rows missing a name. Choices normalize to ``{value, label}`` dicts —
    a plain string is both value and label."""
    rows = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        choices = []
        raw_choices = item.get("choices")
        for choice in raw_choices if isinstance(raw_choices, list) else []:
            if isinstance(choice, dict):
                value = str(choice.get("value") or "").strip()
                label = str(choice.get("label") or value).strip()
            else:
                value = label = str(choice or "").strip()
            if value:
                choices.append({"value": value, "label": label})
        rows.append(
            {
                "name": name,
                "label": str(item.get("label") or "").strip(),
                "help_text": str(item.get("help_text") or "").strip(),
                "required": bool(item.get("required")),
                "data_type": str(item.get("data_type") or "text").strip(),
                "choices": choices,
                "default": str(item.get("default") or "").strip(),
            }
        )
    return rows


def _clean_deadline_rows(items, *, field_names: set[str]) -> list[dict]:
    """Normalize a flow YAML's deadlines; drop rows missing a label, with a
    malformed offset, or whose ``offset_from`` isn't a config field name."""
    rows = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        offset_from = str(item.get("offset_from") or "").strip()
        if not label or offset_from not in field_names:
            continue
        try:
            offset_days = int(item.get("offset_days") or 0)
        except (TypeError, ValueError):
            continue
        rows.append(
            {
                "label": label,
                "description": str(item.get("description") or "").strip(),
                "offset_days": offset_days,
                "offset_from": offset_from,
            }
        )
    return rows


def _clean_form_rows(items, *, forms_dir) -> list[dict]:
    """Normalize a flow YAML's forms; drop rows missing a slug or whose PDF
    is missing from the topic's ``forms/`` dir. The absolute path rides
    along as ``file_path`` for the library apply."""
    rows = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug") or "").strip()
        file_name = str(item.get("file") or "").strip()
        if not slug or not file_name:
            continue
        file_path = forms_dir / file_name
        if not file_path.is_file():
            continue
        rows.append(
            {
                "slug": slug,
                "name": str(item.get("name") or slug).strip(),
                "file": file_name,
                "file_path": str(file_path),
                "mappings": _clean_rows(
                    item.get("fields"),
                    fields=("pdf_field", "template", "checked_when"),
                    required="pdf_field",
                ),
            }
        )
    return rows


def _clean_flow_config(raw: dict, *, fallback_slug: str, topic_dir) -> dict:
    """Normalize a flow YAML into the TopicFlow model shape."""
    sections = []
    for item in (
        raw.get("sections") if isinstance(raw.get("sections"), list) else []
    ):
        if not isinstance(item, dict):
            continue
        heading = str(item.get("heading") or "").strip()
        if heading:
            sections.append(
                {"heading": heading, "content": str(item.get("content") or "")}
            )
    fields = _clean_field_rows(raw.get("fields"))
    return {
        "slug": str(raw.get("slug") or fallback_slug).strip(),
        "name": str(raw.get("name") or fallback_slug).strip(),
        "sections": sections,
        "fields": fields,
        "links": _clean_rows(
            raw.get("links"), fields=("name", "url"), required="name"
        ),
        "deadlines": _clean_deadline_rows(
            raw.get("deadlines"),
            field_names={row["name"] for row in fields},
        ),
        "forms": _clean_form_rows(
            raw.get("forms"), forms_dir=topic_dir / "forms"
        ),
    }


def topic_library_list() -> list[dict]:
    """Topic configs (with their flows) from
    ``library/courts/<court>/topics/<topic>/`` for the admin library."""
    court_names = {
        entry["slug"]: entry["name"] for entry in court_library_list()
    }
    entries = []
    for path in sorted(_COURTS_DIR.glob("*/topics/*/config.yml")):
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            continue
        if not isinstance(raw, dict):
            continue
        topic_dir = path.parent
        court_slug = topic_dir.parent.parent.name
        prompts = raw.get("prompts")
        flows = []
        for flow_path in sorted((topic_dir / "flows").glob("*.yml")):
            try:
                flow_raw = yaml.safe_load(
                    flow_path.read_text(encoding="utf-8")
                )
            except (OSError, yaml.YAMLError):
                continue
            if not isinstance(flow_raw, dict):
                continue
            flows.append(
                _clean_flow_config(
                    flow_raw,
                    fallback_slug=flow_path.stem,
                    topic_dir=topic_dir,
                )
            )
        entries.append(
            {
                "court_slug": court_slug,
                "court_name": court_names.get(court_slug, court_slug),
                "slug": topic_dir.name,
                "title": str(raw.get("title") or topic_dir.name).strip(),
                "subtitle": str(raw.get("subtitle") or "").strip(),
                "description": str(raw.get("description") or "").strip(),
                "icon": str(raw.get("icon") or "").strip(),
                "meta_description": str(
                    raw.get("meta_description") or ""
                ).strip(),
                "prompts": [
                    str(p).strip()
                    for p in (prompts if isinstance(prompts, list) else [])
                    if str(p).strip()
                ],
                "flows": flows,
            }
        )
    return entries


def topic_library_get(*, court_slug: str, topic_slug: str) -> dict | None:
    """A single topic config by court and topic slug, or ``None``."""
    return next(
        (
            e
            for e in topic_library_list()
            if e["court_slug"] == court_slug and e["slug"] == topic_slug
        ),
        None,
    )
