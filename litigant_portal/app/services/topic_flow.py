import io
import math
import re
from datetime import date, datetime, timedelta
from functools import wraps
from string import Formatter

import vobject
import yaml
from django.core.cache import cache
from django.db import transaction
from django.db.models import Max
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from pypdf import PdfReader, PdfWriter

# vobject's own UTC tzinfo — stdlib ``timezone.utc`` has no TZID vobject can
# serialize (see topic_flow/artifacts.py, whose output format this mirrors).
from vobject.icalendar import utc

from litigant_portal.app.models import (
    Topic,
    TopicFlow,
    TopicFlowAnswer,
    TopicFlowDeadline,
    TopicFlowField,
    TopicFlowFieldGroup,
    TopicFlowForm,
    TopicFlowFormField,
    TopicFlowLink,
    TopicFlowSection,
    UserIdentity,
)
from litigant_portal.app.selectors.topic_flow import (
    TOPIC_LIST_CACHE_KEY,
    topic_flow_answer_values,
)
from litigant_portal.app.services.utils import row_move, unique_slug

DataType = TopicFlowField.DataType

_PRODID = "-//Free Law Project//Litigant Portal Topic Flow//EN"

# --- Markdown -------------------------------------------------------------
# Escape-first mini renderer mirroring static/js/admin.js's
# ``renderFlowMarkdown``: paragraphs, dash lists, links, bold/italic.

_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_MD_BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
_MD_EM_RE = re.compile(r"\*([^*]+)\*")
_MD_SAFE_URL_RE = re.compile(r"^(https?:|mailto:)", re.IGNORECASE)
_MD_LIST_RE = re.compile(r"^\s*-\s+")


def _md_escape(text) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _md_link(match: re.Match) -> str:
    label, url = match.group(1), match.group(2)
    safe = url if _MD_SAFE_URL_RE.match(url) else "#"
    return (
        f'<a href="{safe}" target="_blank" rel="noopener noreferrer"'
        f' class="text-primary-700 underline hover:no-underline">{label}</a>'
    )


def _md_inline(text: str) -> str:
    text = _MD_LINK_RE.sub(_md_link, _md_escape(text))
    text = _MD_BOLD_RE.sub(r'<strong class="font-semibold">\1</strong>', text)
    return _MD_EM_RE.sub(r'<em class="italic">\1</em>', text)


def render_markdown(text) -> str:
    """Authored flow copy -> safe HTML. Every character is HTML-escaped
    before markup is added, so the result is safe to render directly."""
    lines = str(text or "").split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if _MD_LIST_RE.match(line):
            items = []
            while i < len(lines) and _MD_LIST_RE.match(lines[i]):
                item = _MD_LIST_RE.sub("", lines[i], count=1)
                items.append(f"<li>{_md_inline(item)}</li>")
                i += 1
            out.append(
                '<ul class="list-disc pl-5 my-2 space-y-0.5">'
                + "".join(items)
                + "</ul>"
            )
            continue
        out.append(
            f'<p class="my-2 first:mt-0 last:mb-0">{_md_inline(line)}</p>'
        )
        i += 1
    return mark_safe("".join(out))


# --- Answers --------------------------------------------------------------


def _answer_validate(field: TopicFlowField, value):
    """Coerce a submitted answer per the field's data type; raises
    ``ValueError`` on invalid input."""
    if field.data_type == DataType.DATE:
        try:
            return date.fromisoformat(str(value)).isoformat()
        except ValueError:
            raise ValueError(_("Invalid date for %s") % field.name)
    if field.data_type == DataType.DATETIME:
        try:
            return datetime.fromisoformat(str(value)).isoformat()
        except ValueError:
            raise ValueError(_("Invalid datetime for %s") % field.name)
    if field.data_type == DataType.NUMBER:
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(_("Invalid number for %s") % field.name)
        if not math.isfinite(number):
            raise ValueError(_("Invalid number for %s") % field.name)
        return int(number) if number.is_integer() else number
    if field.data_type == DataType.BOOLEAN:
        return bool(value)
    if field.data_type == DataType.CHOICE:
        value = str(value)
        if value not in {choice["value"] for choice in field.choices}:
            raise ValueError(_("Invalid choice for %s") % field.name)
        return value
    return str(value)


def topic_flow_answers_update(
    *, identity: UserIdentity, flow: TopicFlow, answers: dict
) -> dict:
    """Store validated ``answers`` for the flow's fields (unknown names are
    ignored, null/empty clears); returns the current values map. Raises
    ``ValueError`` on an invalid value."""
    with transaction.atomic():
        for field in flow.fields:
            if field.name not in answers:
                continue
            value = answers[field.name]
            if value is None or value == "":
                TopicFlowAnswer.objects.filter(
                    identity=identity, field=field
                ).delete()
                continue
            TopicFlowAnswer.objects.update_or_create(
                identity=identity,
                field=field,
                defaults={"value": _answer_validate(field, value)},
            )
    return topic_flow_answer_values(identity=identity, flow=flow)


def _coerce_date(value) -> date | None:
    """A stored date/datetime answer as a ``date``, or ``None``."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except (TypeError, ValueError):
        return None


def _python_values(flow: TopicFlow, values: dict) -> dict:
    """Stored answer values (an authored field default filling in for an
    unanswered field) with date/datetime answers coerced to ``date``
    objects per the field's data type (for template formatting)."""
    out = dict(values)
    for field in flow.fields:
        if field.name not in out and field.default:
            out[field.name] = field.default
        if (
            field.data_type in (DataType.DATE, DataType.DATETIME)
            and field.name in out
        ):
            out[field.name] = _coerce_date(out[field.name])
    return out


def topic_flow_deadline_rows(*, flow: TopicFlow, values: dict) -> list[dict]:
    """Each flow deadline with its computed date — the offset field's date
    answer plus ``offset_days``, or ``None`` while unanswered."""
    rows = []
    for deadline in flow.deadlines.all():
        answered = _coerce_date(values.get(deadline.offset_from.name))
        rows.append(
            {
                "label": deadline.label,
                "description": deadline.description,
                "date": (
                    answered + timedelta(days=deadline.offset_days)
                    if answered
                    else None
                ),
            }
        )
    return rows


def topic_flow_sample_values(*, flow: TopicFlow) -> dict:
    """Per-data-type sample answers for the admin form preview."""
    values = {}
    for field in flow.fields:
        if field.data_type in (DataType.DATE, DataType.DATETIME):
            values[field.name] = date(2026, 1, 15)
        elif field.data_type == DataType.NUMBER:
            values[field.name] = 42
        elif field.data_type == DataType.BOOLEAN:
            values[field.name] = True
        elif field.data_type == DataType.CHOICE:
            values[field.name] = next(
                (choice["value"] for choice in field.choices), ""
            )
        else:
            values[field.name] = "Sample text"
    return values


# --- PDF forms ------------------------------------------------------------


class _SafeFormatter(Formatter):
    """``str.format`` over answer values: a missing/unanswered field renders
    as "" (never KeyError), even under a format spec like ``{dob:%Y}``."""

    def get_value(self, key, args, kwargs):
        value = kwargs.get(key) if isinstance(key, str) else ""
        return "" if value is None else value

    def format_field(self, value, format_spec):
        if value == "" and format_spec:
            return ""
        return super().format_field(value, format_spec)


_FORMATTER = _SafeFormatter()


def _resolve_template(template: str, values: dict) -> str:
    """Format ``template`` against ``values``; a malformed template (or
    dotted/indexed access into a missing answer's "") renders as "".
    Space runs left by a blank optional field (e.g. a missing middle name
    in ``{first} {middle} {last}``) collapse to a single space."""
    try:
        resolved = _FORMATTER.vformat(template, (), values)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError):
        return ""
    return re.sub(r" {2,}", " ", resolved).strip()


def _on_state(field) -> str | None:
    """A /Btn field's checked state name (the one that isn't /Off)."""
    for state in field.get("/_States_") or []:
        if state != "/Off":
            return state
    return None


def topic_flow_form_pdf_fields(*, form: TopicFlowForm) -> list[dict]:
    """The form PDF's fillable fields as ``{name, type, on_state}`` rows."""
    rows = []
    with form.file.open("rb") as fh:
        for name, field in (PdfReader(fh).get_fields() or {}).items():
            field_type = field.get("/FT")
            if field_type == "/Btn":
                on_state = _on_state(field)
                rows.append(
                    {
                        "name": name,
                        "type": "checkbox",
                        "on_state": on_state and on_state.lstrip("/"),
                    }
                )
            else:
                rows.append(
                    {
                        "name": name,
                        "type": "text" if field_type == "/Tx" else "other",
                        "on_state": None,
                    }
                )
    return rows


def _checkbox_on(resolved: str, checked_when: str) -> bool:
    if checked_when:
        return resolved == checked_when
    return resolved.strip() not in ("", "false", "False", "None", "0")


def _fill_form_pdf(form: TopicFlowForm, resolved: dict) -> bytes:
    """Fill ``form``'s PDF from already field-resolved ``resolved`` values."""
    with form.file.open("rb") as fh:
        reader = PdfReader(fh)
        writer = PdfWriter(clone_from=reader)
        pdf_fields = reader.get_fields() or {}
        fill = {}
        for mapping in form.mappings.all():
            value = _resolve_template(mapping.template, resolved)
            field = pdf_fields.get(mapping.pdf_field)
            if field is not None and field.get("/FT") == "/Btn":
                if _checkbox_on(value, mapping.checked_when):
                    state = _on_state(field)
                    if state:
                        fill[mapping.pdf_field] = state
                else:
                    fill[mapping.pdf_field] = "/Off"
            else:
                fill[mapping.pdf_field] = value
        for page in writer.pages:
            writer.update_page_form_field_values(page, fill)
        buffer = io.BytesIO()
        writer.write(buffer)
    return buffer.getvalue()


def topic_flow_form_fill(
    *, form: TopicFlowForm, values: dict, flow: TopicFlow | None = None
) -> bytes:
    """Fill ``form``'s PDF from answer ``values`` via its mappings."""
    return _fill_form_pdf(form, _python_values(flow or form.flow, values))


def topic_flow_packet(*, flow: TopicFlow, values: dict) -> bytes:
    """Every flow form filled and merged into one PDF, in form order."""
    resolved = _python_values(flow, values)
    writer = PdfWriter()
    for form in flow.forms.all():
        writer.append(io.BytesIO(_fill_form_pdf(form, resolved)))
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


# --- Calendar / contacts --------------------------------------------------
# Mirrors the legacy engine's output format (topic_flow/artifacts.py):
# all-day VALUE=DATE events with stable UIDs; org-style vCards.


def topic_flow_calendar_ics(*, flow: TopicFlow, values: dict) -> str:
    """The flow's computed deadlines as an iCalendar string; deadlines
    whose date field is unanswered yield no event."""
    cal = vobject.iCalendar()
    cal.add("prodid").value = _PRODID
    generated_at = datetime.now(utc)
    rows = topic_flow_deadline_rows(flow=flow, values=values)
    for deadline, row in zip(flow.deadlines.all(), rows):
        if row["date"] is None:
            continue
        vevent = cal.add("vevent")
        vevent.add(
            "uid"
        ).value = (
            f"{flow.topic.slug}-{flow.slug}-{deadline.id}@litigantportal.com"
        )
        vevent.add("dtstamp").value = generated_at
        vevent.add("summary").value = row["label"]
        vevent.add("dtstart").value = row["date"]
        if row["description"]:
            vevent.add("description").value = row["description"]
    return cal.serialize()


# Flow data types -> docassemble field datatypes.
_DOCASSEMBLE_DATATYPES = {
    DataType.TEXT: "text",
    DataType.DATE: "date",
    DataType.DATETIME: "datetime",
    DataType.NUMBER: "number",
    DataType.BOOLEAN: "yesno",
    DataType.CHOICE: "dropdown",
}


def topic_flow_interview_yaml(*, flow: TopicFlow) -> str:
    """The flow's interview as a docassemble-compatible YAML document.

    Field groups map one-to-one onto docassemble ``question`` screens
    (``title`` -> ``question``, ``description`` -> ``subquestion``, the
    group's fields -> the screen's ``fields``), so an interview built
    here can run unchanged in a docassemble container: a ``mandatory``
    code block walks the fields in interview order, and a terminal
    ``event`` screen ends the interview.
    """
    order_vars = []
    question_blocks = []
    for group in flow.field_groups.all():
        rows = []
        for field in group.fields.all():
            order_vars.append(field.name)
            row = {
                "label": field.label or field.name,
                "field": field.name,
                "datatype": _DOCASSEMBLE_DATATYPES.get(
                    field.data_type, "text"
                ),
                # docassemble fields are required unless told otherwise.
                "required": bool(field.required),
            }
            if field.help_text:
                row["help"] = field.help_text
            if field.default:
                row["default"] = field.default
            if field.data_type == DataType.CHOICE:
                row["choices"] = [
                    {choice["label"]: choice["value"]}
                    for choice in field.choices
                    if isinstance(choice, dict) and choice.get("value")
                ]
            rows.append(row)
        if not rows:
            continue
        block = {"question": group.title or flow.name}
        if group.description:
            block["subquestion"] = group.description
        block["fields"] = rows
        question_blocks.append(block)
    blocks = [
        {"metadata": {"title": flow.name}},
        {
            "mandatory": True,
            "code": "\n".join([*order_vars, "interview_complete"]),
        },
        *question_blocks,
        {
            "event": "interview_complete",
            "question": _("All done"),
            "subquestion": _(
                "You have answered every question in this interview."
            ),
        },
    ]
    return yaml.safe_dump_all(
        blocks, sort_keys=False, allow_unicode=True, default_flow_style=False
    )


# --- Authoring ------------------------------------------------------------
# The admin dashboard's piecemeal CRUD over topics, flows, and each flow
# collection. Library applies (bulk upserts from the content dir) live in
# services/library.py.


def busts_topic_list_cache(fn):
    """Busts the cached topic list."""

    @wraps(fn)
    def wrapped(*args, **kwargs):
        result = fn(*args, **kwargs)
        transaction.on_commit(lambda: cache.delete(TOPIC_LIST_CACHE_KEY))
        return result

    return wrapped


@busts_topic_list_cache
def topic_create(**fields) -> Topic:
    """Create a topic."""
    last = Topic.objects.aggregate(m=Max("order"))["m"]
    return Topic.objects.create(
        slug=unique_slug(Topic.objects, fields["title"], "topic"),
        order=0 if last is None else last + 1,
        **fields,
    )


@busts_topic_list_cache
def topic_update(*, topic: Topic, **fields) -> Topic:
    """Update a topic's editable fields."""
    for name, value in fields.items():
        setattr(topic, name, value)
    topic.save(update_fields=[*fields, "updated_at"])
    return topic


@busts_topic_list_cache
def topic_delete(*, topic: Topic) -> None:
    topic.delete()


@busts_topic_list_cache
def topic_move(*, topic: Topic, direction: str) -> None:
    """Move a topic one step up or down in the display order."""
    with transaction.atomic():
        row_move(list(Topic.objects.all()), topic, direction)


@busts_topic_list_cache
def topic_flow_create(*, topic: Topic, slug: str, name: str) -> TopicFlow:
    """Create an empty flow on ``topic`` (the create-flow modal)."""
    return TopicFlow.objects.create(topic=topic, slug=slug, name=name)


@busts_topic_list_cache
def topic_flow_content_update(*, flow: TopicFlow, sections: list) -> TopicFlow:
    """Replace just a flow's content sections (the content editor's Save)."""
    with transaction.atomic():
        flow.sections.all().delete()
        TopicFlowSection.objects.bulk_create(
            TopicFlowSection(flow=flow, order=i, **row)
            for i, row in enumerate(sections)
        )
        flow.save(update_fields=["updated_at"])
    return flow


@busts_topic_list_cache
def topic_flow_details_update(
    *, flow: TopicFlow, name: str, slug: str
) -> TopicFlow:
    """Update a flow's name and slug (the flow page's inline form)."""
    flow.name = name
    flow.slug = slug
    flow.save(update_fields=["name", "slug", "updated_at"])
    return flow


@busts_topic_list_cache
def topic_flow_delete(*, flow: TopicFlow) -> None:
    flow.delete()


@busts_topic_list_cache
def topic_flow_enabled_update(*, flow: TopicFlow, enabled: bool) -> TopicFlow:
    """Set whether a flow is live (the topic card's Draft/Live switch)."""
    flow.enabled = enabled
    flow.save(update_fields=["enabled", "updated_at"])
    return flow


@busts_topic_list_cache
def topic_flow_field_group_create(
    *, flow: TopicFlow, **fields
) -> TopicFlowFieldGroup:
    """Create an interview page on ``flow``, appended to the page order."""
    last = flow.field_groups.aggregate(m=Max("order"))["m"]
    return TopicFlowFieldGroup.objects.create(
        flow=flow, order=0 if last is None else last + 1, **fields
    )


@busts_topic_list_cache
def topic_flow_field_group_update(
    *, group: TopicFlowFieldGroup, **fields
) -> TopicFlowFieldGroup:
    """Update an interview page's editable fields."""
    for name, value in fields.items():
        setattr(group, name, value)
    group.save(update_fields=[*fields, "updated_at"])
    return group


@busts_topic_list_cache
def topic_flow_field_group_move(
    *, group: TopicFlowFieldGroup, direction: str
) -> None:
    """Move an interview page one step up or down in its flow."""
    with transaction.atomic():
        row_move(list(group.flow.field_groups.all()), group, direction)


@busts_topic_list_cache
def topic_flow_field_group_delete(*, group: TopicFlowFieldGroup) -> None:
    """Delete an interview page and its fields — cascading to litigants'
    saved answers and any deadlines based on those fields."""
    with transaction.atomic():
        flow = group.flow
        group.delete()
        for position, obj in enumerate(flow.field_groups.all()):
            if obj.order != position:
                obj.order = position
                obj.save(update_fields=["order", "updated_at"])


@busts_topic_list_cache
def topic_flow_field_create(
    *, group: TopicFlowFieldGroup, **fields
) -> TopicFlowField:
    """Create a field on an interview page, appended to the field order."""
    last = group.fields.aggregate(m=Max("order"))["m"]
    return TopicFlowField.objects.create(
        group=group, order=0 if last is None else last + 1, **fields
    )


@busts_topic_list_cache
def topic_flow_field_update(
    *, field: TopicFlowField, **fields
) -> TopicFlowField:
    """Update a field's editable attributes."""
    for name, value in fields.items():
        setattr(field, name, value)
    field.save(update_fields=[*fields, "updated_at"])
    return field


@busts_topic_list_cache
def topic_flow_field_group_change(
    *, field: TopicFlowField, group: TopicFlowFieldGroup
) -> TopicFlowField:
    """Move a field to the end of another interview page, renumbering
    the page it left so its orders stay dense."""
    if group.id == field.group_id:
        return field
    with transaction.atomic():
        source = field.group
        last = group.fields.aggregate(m=Max("order"))["m"]
        field.group = group
        field.order = 0 if last is None else last + 1
        field.save(update_fields=["group", "order", "updated_at"])
        for position, obj in enumerate(source.fields.all()):
            if obj.order != position:
                obj.order = position
                obj.save(update_fields=["order", "updated_at"])
    return field


@busts_topic_list_cache
def topic_flow_field_move(*, field: TopicFlowField, direction: str) -> None:
    """Move a field one step up or down within its interview page."""
    with transaction.atomic():
        row_move(list(field.group.fields.all()), field, direction)


@busts_topic_list_cache
def topic_flow_field_delete(*, field: TopicFlowField) -> None:
    """Delete a field — cascading to litigants' saved answers and any
    deadlines based on it — and renumber its page's remaining fields."""
    with transaction.atomic():
        group = field.group
        field.delete()
        for position, obj in enumerate(group.fields.all()):
            if obj.order != position:
                obj.order = position
                obj.save(update_fields=["order", "updated_at"])


@busts_topic_list_cache
def topic_flow_deadline_create(
    *, flow: TopicFlow, **fields
) -> TopicFlowDeadline:
    """Create a deadline on ``flow``, appended to the display order."""
    last = flow.deadlines.aggregate(m=Max("order"))["m"]
    return TopicFlowDeadline.objects.create(
        flow=flow, order=0 if last is None else last + 1, **fields
    )


@busts_topic_list_cache
def topic_flow_deadline_update(
    *, deadline: TopicFlowDeadline, **fields
) -> TopicFlowDeadline:
    """Update a deadline's editable fields."""
    for name, value in fields.items():
        setattr(deadline, name, value)
    deadline.save(update_fields=[*fields, "updated_at"])
    return deadline


@busts_topic_list_cache
def topic_flow_deadline_delete(*, deadline: TopicFlowDeadline) -> None:
    deadline.delete()


@busts_topic_list_cache
def topic_flow_deadline_move(
    *, deadline: TopicFlowDeadline, direction: str
) -> None:
    """Move a deadline one step up or down in its flow's display order."""
    with transaction.atomic():
        row_move(list(deadline.flow.deadlines.all()), deadline, direction)


@busts_topic_list_cache
def topic_flow_link_create(*, flow: TopicFlow, **fields) -> TopicFlowLink:
    """Create a link on ``flow``, appended to the display order."""
    last = flow.links.aggregate(m=Max("order"))["m"]
    return TopicFlowLink.objects.create(
        flow=flow, order=0 if last is None else last + 1, **fields
    )


@busts_topic_list_cache
def topic_flow_link_update(*, link: TopicFlowLink, **fields) -> TopicFlowLink:
    """Update a link's editable fields."""
    for name, value in fields.items():
        setattr(link, name, value)
    link.save(update_fields=[*fields, "updated_at"])
    return link


@busts_topic_list_cache
def topic_flow_link_delete(*, link: TopicFlowLink) -> None:
    link.delete()


@busts_topic_list_cache
def topic_flow_link_move(*, link: TopicFlowLink, direction: str) -> None:
    """Move a link one step up or down in its flow's display order."""
    with transaction.atomic():
        row_move(list(link.flow.links.all()), link, direction)


@busts_topic_list_cache
def topic_flow_form_mappings_replace(
    form: TopicFlowForm, mappings: list
) -> None:
    """Replace a form's PDF field mappings wholesale, in order."""
    form.mappings.all().delete()
    TopicFlowFormField.objects.bulk_create(
        TopicFlowFormField(form=form, order=i, **row)
        for i, row in enumerate(mappings)
    )


@busts_topic_list_cache
def topic_flow_form_create(
    *, flow: TopicFlow, name: str, file
) -> TopicFlowForm:
    """Attach an uploaded PDF form to ``flow``, appended to the form order."""
    last = flow.forms.aggregate(m=Max("order"))["m"]
    return TopicFlowForm.objects.create(
        flow=flow,
        slug=unique_slug(flow.forms, name, "form"),
        name=name,
        file=file,
        order=0 if last is None else last + 1,
    )


@busts_topic_list_cache
def topic_flow_form_update(
    *, form: TopicFlowForm, name: str, mappings: list
) -> TopicFlowForm:
    """Save a form's name and field mappings (the form editor's Save)."""
    with transaction.atomic():
        form.name = name
        form.save(update_fields=["name", "updated_at"])
        topic_flow_form_mappings_replace(form, mappings)
    return form


@busts_topic_list_cache
def topic_flow_form_delete(*, form: TopicFlowForm) -> None:
    form.delete()


@busts_topic_list_cache
def topic_flow_form_move(*, form: TopicFlowForm, direction: str) -> None:
    """Move a form one step up or down in its flow's display order."""
    with transaction.atomic():
        row_move(list(form.flow.forms.all()), form, direction)
