"""Topic flow tools: load a guide, set the active guide, save answers,
and read a form.

App imports stay inside functions — ``litigant_portal.app.models`` imports
this package's message schema, so module-level app imports would be
circular.
"""

import json
from typing import Any

from django.urls import reverse

from litigant_portal.agents.base import Field, Tool, ToolOutput

NO_ACTIVE_FLOW = (
    "Error: no active guide. Call SetActiveTopicFlow first (available "
    "guides are listed in your instructions)."
)


def topic_flow_find(*, topic_slug: str, flow_slug: str):
    """A live flow by slugs from the cached topic list, or ``None``."""
    from litigant_portal.app.selectors.topic_flow import topic_list

    for topic in topic_list():
        if topic.slug != topic_slug:
            continue
        for flow in topic.flows.all():
            if flow.slug == flow_slug and flow.enabled:
                return flow
    return None


def topic_flow_catalog_lines() -> list[str]:
    """One line per live guide, for the system prompt and error results.

    The args are spelled out per line because small models misparse a
    combined ``topic/flow`` pair as the topic_slug alone."""
    from litigant_portal.app.selectors.topic_flow import topic_list

    return [
        f'- topic_slug "{topic.slug}", flow_slug "{flow.slug}": '
        f"{flow.name} (topic: {topic.title})"
        for topic in topic_list()
        for flow in topic.flows.all()
        if flow.enabled
    ]


def topic_flow_resolve(*, topic_slug: str, flow_slug: str):
    """A live flow from the arg shapes models actually produce.

    Tolerates the combined catalog pair landing in either argument
    ("eviction/tenant" as the topic_slug) and, as a last resort, the
    flow's display name passed in place of its slug."""
    from litigant_portal.app.selectors.topic_flow import topic_list

    raw_topic = (topic_slug or "").strip().strip("/")
    raw_flow = (flow_slug or "").strip().strip("/")
    candidates = [(raw_topic, raw_flow)]
    if "/" in raw_topic:
        first, _, rest = raw_topic.partition("/")
        candidates.append((first, rest))
    if "/" in raw_flow:
        first, _, rest = raw_flow.partition("/")
        candidates.append((first, rest))
    for topic, flow in candidates:
        found = topic_flow_find(
            topic_slug=topic.lower(), flow_slug=flow.lower()
        )
        if found is not None:
            return found
    names = {raw_topic.lower(), raw_flow.lower()}
    by_name = [
        flow
        for topic in topic_list()
        for flow in topic.flows.all()
        if flow.enabled and flow.name.lower() in names
    ]
    return by_name[0] if len(by_name) == 1 else None


def _flow_page_url(flow) -> str:
    return reverse(
        "pages:topic_flow",
        kwargs={"topic_slug": flow.topic.slug, "flow_slug": flow.slug},
    )


def _field_status_line(field, values: dict) -> str:
    """One field as ``- name [spec] (label): value``."""
    spec = field.data_type
    if field.required:
        spec += ", required"
    if field.data_type == "choice":
        options = ", ".join(
            str(choice.get("value", "")) for choice in field.choices
        )
        spec += f"; options: {options}"
    label = ""
    if field.label and field.label != field.name:
        label = f" ({field.label})"
    if field.name in values:
        value = json.dumps(values[field.name])
    elif field.default:
        value = f"not answered (default: {field.default!r})"
    else:
        value = "not answered"
    return f"- {field.name} [{spec}]{label}: {value}"


def topic_flow_status_text(*, flow, identity) -> str:
    """Compact live status of ``flow`` for prompts and tool results:
    interview progress, fields with current answers, deadlines, and forms."""
    from litigant_portal.app.selectors.topic_flow import (
        topic_flow_answer_values,
        topic_flow_fields,
    )
    from litigant_portal.app.services.topic_flow import (
        topic_flow_deadline_rows,
        topic_flow_progress,
    )

    values = topic_flow_answer_values(identity=identity, flow=flow)
    answered, total = topic_flow_progress(flow=flow, values=values)
    lines = [
        f"Guide: {flow.name} ({flow.topic.slug}/{flow.slug})",
        f"Guide page (share this link with the user): {_flow_page_url(flow)}",
    ]
    fields = topic_flow_fields(flow=flow)
    if fields:
        lines.append(f"Interview progress: {answered} of {total} answered.")
        lines.append("Fields (save with UpdateTopicFlowFields):")
        lines.extend(_field_status_line(field, values) for field in fields)
    deadlines = list(flow.deadlines.all())
    if deadlines:
        lines.append("Deadlines:")
        rows = topic_flow_deadline_rows(flow=flow, values=values)
        for deadline, row in zip(deadlines, rows):
            when = (
                row["date"].isoformat()
                if row["date"]
                else f"unknown until {deadline.offset_from.name} is answered"
            )
            lines.append(f"- {row['label']}: {when}")
    forms = list(flow.forms.all())
    if forms:
        lines.append("Forms (auto-filled from answers; see ReadForm):")
        lines.extend(f"- {form.slug}: {form.name}" for form in forms)
    return "\n".join(lines)


def _unknown_flow_result(topic_slug: str, flow_slug: str) -> ToolOutput:
    catalog = "\n".join(topic_flow_catalog_lines()) or "(none)"
    return ToolOutput(
        result=(
            f"Error: no guide {topic_slug}/{flow_slug}. Available guides:\n"
            f"{catalog}"
        )
    )


def _active_flow(thread):
    """The thread's active flow, or ``None`` when unset or no longer live."""
    from litigant_portal.agents.assistant import LitigantAssistantState

    state = LitigantAssistantState.model_validate(thread.state or {})
    ref = state.active_topic_flow
    if ref is None:
        return None
    return topic_flow_find(topic_slug=ref.topic_slug, flow_slug=ref.flow_slug)


class LoadTopicFlow(Tool):
    """Load a guide's full content: its explanation sections, interview
    fields with the user's current answers, deadlines, forms, and links.

    Use this before walking the user through a guide's process or
    answering questions the guide covers. Guides are listed in your
    instructions as topic-slug/flow-slug pairs.
    """

    topic_slug: str = Field(description="The guide's topic slug")
    flow_slug: str = Field(description="The guide's flow slug")

    tool_call_template = "tools/load_topic_flow_call.html"
    tool_result_template = "tools/load_topic_flow_result.html"

    def __call__(self, *, thread_id) -> ToolOutput:
        from litigant_portal.app.models import ChatThread

        flow = topic_flow_resolve(
            topic_slug=self.topic_slug, flow_slug=self.flow_slug
        )
        if flow is None:
            return _unknown_flow_result(self.topic_slug, self.flow_slug)

        thread = ChatThread.objects.get(id=thread_id)
        parts = [topic_flow_status_text(flow=flow, identity=thread.identity)]
        sections = list(flow.sections.all())
        if sections:
            parts.append("Guide content:")
            for section in sections:
                parts.append(f"## {section.heading}\n{section.content}")
        links = list(flow.links.all())
        if links:
            parts.append(
                "Links:\n"
                + "\n".join(f"- {link.name}: {link.url}" for link in links)
            )
        return ToolOutput(
            result="\n\n".join(parts),
            render_data={
                "name": flow.name,
                "topic_title": flow.topic.title,
            },
        )


class SetActiveTopicFlow(Tool):
    """Set the guide (topic flow) this conversation works from.

    Call this as soon as the user's situation matches one of the available
    guides. The active guide's live field status is kept in your
    instructions, and the user sees a guide card with forms and progress
    in their sidebar.
    """

    topic_slug: str = Field(description="The guide's topic slug")
    flow_slug: str = Field(description="The guide's flow slug")

    tool_call_template = "tools/set_active_topic_flow_call.html"
    tool_result_template = "tools/set_active_topic_flow_result.html"

    def __call__(self, *, thread_id) -> ToolOutput:
        from litigant_portal.agents.assistant import (
            ActiveTopicFlowRef,
            LitigantAssistantState,
        )
        from litigant_portal.app.models import ChatThread

        flow = topic_flow_resolve(
            topic_slug=self.topic_slug, flow_slug=self.flow_slug
        )
        if flow is None:
            return _unknown_flow_result(self.topic_slug, self.flow_slug)

        # Canonical slugs from the resolved flow, not the raw args — the
        # resolver may have repaired them.
        slugs = {"topic_slug": flow.topic.slug, "flow_slug": flow.slug}
        thread = ChatThread.objects.get(id=thread_id)
        state = LitigantAssistantState.model_validate(thread.state or {})
        state.active_topic_flow = ActiveTopicFlowRef(
            topic_slug=flow.topic.slug,
            flow_slug=flow.slug,
            summary_url=reverse("topic_flow_api:summary", kwargs=slugs),
        )
        thread.state = state.model_dump()
        thread.save(update_fields=["state", "updated_at"])

        return ToolOutput(
            result=(
                f"Active guide is now {flow.name} "
                f"({flow.topic.slug}/{flow.slug}). Its live field "
                "status appears in your instructions. Use LoadTopicFlow to "
                "read its full content."
            ),
            render_data={
                "name": flow.name,
                "topic_title": flow.topic.title,
                "url": _flow_page_url(flow),
            },
            refresh_system_prompt=True,
        )


class UpdateTopicFlowFields(Tool):
    """Save the user's answers to the active guide's interview fields.

    Call this the moment the user shares a fact that answers a field.
    Partial updates are preferred; never wait until every field is known.
    The guide's forms and deadlines update automatically from the answers.
    """

    fields: dict[str, Any] = Field(
        description=(
            "Map of guide field name to value. Match each field's data "
            "type (dates as YYYY-MM-DD). Pass null or an empty string to "
            "clear a field."
        )
    )

    tool_call_template = "tools/update_topic_flow_fields_call.html"
    tool_result_template = "tools/update_topic_flow_fields_result.html"

    def __call__(self, *, thread_id) -> ToolOutput:
        from litigant_portal.app.models import ChatThread
        from litigant_portal.app.selectors.topic_flow import (
            topic_flow_fields,
        )
        from litigant_portal.app.services.topic_flow import (
            topic_flow_answers_update,
        )

        thread = ChatThread.objects.get(id=thread_id)
        flow = _active_flow(thread)
        if flow is None:
            return ToolOutput(result=NO_ACTIVE_FLOW)

        labels = {
            field.name: field.label or field.name
            for field in topic_flow_fields(flow=flow)
        }
        unknown = sorted(set(self.fields) - set(labels))
        try:
            values = topic_flow_answers_update(
                identity=thread.identity,
                flow=flow,
                answers=self.fields,
                reviewed=False,
            )
        except ValueError as error:
            return ToolOutput(
                result=(
                    f"Error: {error}. No answers were saved; fix the value "
                    "and try again."
                )
            )

        saved = []
        cleared = []
        for name in self.fields:
            if name not in labels:
                continue
            (cleared if name not in values else saved).append(name)

        lines = []
        if saved:
            lines.append("Saved: " + ", ".join(saved) + ".")
        if cleared:
            lines.append("Cleared: " + ", ".join(cleared) + ".")
        if unknown:
            lines.append(
                "Unknown field names ignored: " + ", ".join(unknown) + "."
            )
        lines.append(
            "The current answers appear in your instructions under "
            "ACTIVE GUIDE."
        )
        return ToolOutput(
            result=" ".join(lines),
            render_data={
                "flow_name": flow.name,
                "saved": [labels[name] for name in saved],
                "cleared": [labels[name] for name in cleared],
                "unknown": unknown,
            },
            refresh_system_prompt=True,
        )


class ReadForm(Tool):
    """Read one of the active guide's PDF forms: its text, its fillable
    fields, how each is filled from guide answers, and which answers are
    still missing.

    Use this before explaining a form or checking whether it is ready to
    download. Form slugs are listed in the guide status.
    """

    form_slug: str = Field(
        description="Slug of the form, as listed in the guide status"
    )

    tool_call_template = "tools/read_form_call.html"
    tool_result_template = "tools/read_form_result.html"

    def __call__(self, *, thread_id) -> ToolOutput:
        from litigant_portal.app.models import ChatThread
        from litigant_portal.app.selectors.topic_flow import (
            topic_flow_answer_values,
        )
        from litigant_portal.app.services.topic_flow import (
            topic_flow_form_status,
            topic_flow_form_text,
        )

        thread = ChatThread.objects.get(id=thread_id)
        flow = _active_flow(thread)
        if flow is None:
            return ToolOutput(result=NO_ACTIVE_FLOW)

        form = next(
            (f for f in flow.forms.all() if f.slug == self.form_slug), None
        )
        if form is None:
            slugs = ", ".join(f.slug for f in flow.forms.all()) or "(none)"
            return ToolOutput(
                result=(
                    f"Error: the active guide has no form "
                    f"{self.form_slug!r}. Its forms: {slugs}."
                )
            )

        values = topic_flow_answer_values(identity=thread.identity, flow=flow)
        status = topic_flow_form_status(form=form, values=values, flow=flow)
        filled = [row for row in status["mappings"] if row["value"]]
        missing = status["missing_fields"]

        lines = [
            f"Form: {form.name} ({form.slug}) in guide "
            f"{flow.topic.slug}/{flow.slug}",
            f"Fill status: {len(filled)} of {len(status['mappings'])} "
            "mapped PDF fields currently have values.",
        ]
        if missing:
            lines.append(
                "Guide fields still needed by this form: "
                + ", ".join(missing)
                + "."
            )
        if status["mappings"]:
            lines.append("PDF fields (template -> current value):")
            for row in status["mappings"]:
                value = json.dumps(row["value"]) if row["value"] else "(empty)"
                lines.append(
                    f"- {row['pdf_field']} <- {row['template']!r}: {value}"
                )
        text = topic_flow_form_text(form=form)
        if text:
            lines.append(f"Form text (extracted from the PDF):\n{text}")
        return ToolOutput(
            result="\n".join(lines),
            render_data={
                "name": form.name,
                "flow_name": flow.name,
                "filled": len(filled),
                "mapped": len(status["mappings"]),
                "missing": missing,
            },
        )
