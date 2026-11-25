import json

from litigant_portal.agents.base import Field, Tool, ToolOutput
from litigant_portal.state.types import ProjectionType


def topic_flow_path(flow) -> str:
    """The slug path that names ``flow`` in agent state and tool calls."""
    return f"{flow.topic.slug}/{flow.slug}"


def topic_flow_from_path(path: str, *, graph: bool = True):
    """The enabled TopicFlow at ``path`` (topic-slug/flow-slug), or None.
    ``graph`` is passed to ``topic_flow_find``."""
    from litigant_portal.app.selectors.topic_flow import topic_flow_find

    topic_slug, sep, flow_slug = path.partition("/")
    if not (sep and topic_slug and flow_slug):
        return None
    return topic_flow_find(
        topic_slug=topic_slug, flow_slug=flow_slug, graph=graph
    )


def _variable_line(variable) -> str:
    line = f"- {variable.name} ({variable.data_type})"
    prompt = variable.question or variable.label
    if prompt:
        line += f": {prompt}"
    if variable.choices:
        values = ", ".join(c["value"] for c in variable.choices)
        line += f" [choices: {values}]"
    if variable.asked_when is not None:
        line += f" (asked when {json.dumps(variable.asked_when)})"
    if help_text := variable.help_text.strip():
        line += f"\n  Help: {help_text}"
    return line


def source_marker(flow, key: str) -> str:
    """The citation marker for one of ``flow``'s blocks, or "" when the
    block has no key (a migrated-but-unsynced or admin-created row). The
    prompt's evidence rules describe this exact shape, so change both
    together."""
    return f"[source:{topic_flow_path(flow)}/{key}]" if key else ""


def cited(marker: str, text: str) -> str:
    """``text`` prefixed by its marker, or alone when there is none."""
    return f"{marker} {text}" if marker else text


def topic_flow_markdown(
    flow, projection: ProjectionType, *, public_names: set[str] | None = None
) -> str:
    """
    Applicable authored content and computed progress for this identity.

    Public names are supplied only for the stored prompt snapshot, where
    dates derived from private source facts must also be masked.
    """
    lines = [f"# {flow.name}", f"Topic: {flow.topic.title}"]
    components = {
        component.id: component for component in projection.components
    }

    for number, section in enumerate(flow.sections.all(), 1):
        if (section.key or f"section-{number}") not in components:
            continue
        heading = f"## {section.heading}"
        marker = source_marker(flow, section.key)
        if marker:
            heading += f" {marker}"
        lines += ["", heading, section.content.strip()]

    resolved = {
        deadline.id: deadline.date for deadline in projection.deadlines
    }
    deadlines = [
        deadline
        for deadline in flow.deadlines.all()
        if deadline.ref in resolved
    ]
    if deadlines:
        lines += ["", "## Deadlines"]
        for d in deadlines:
            anchor = d.offset_from.label or d.offset_from.name
            when = (
                f"{d.offset_days} days after"
                if d.offset_days >= 0
                else f"{-d.offset_days} days before"
            )
            line = f"- {cited(source_marker(flow, d.key), d.label)}: "
            line += f"{when} {anchor}"
            if d.description:
                line += f". {d.description}"
            if resolved[d.ref] is not None:
                computed = (
                    resolved[d.ref].isoformat()
                    if public_names is None
                    or d.offset_from.name in public_names
                    else "[private]"
                )
                line += f". Computed date: {computed}"
            lines.append(line)

    forms = {
        entry.form.slug: entry.form for entry in flow.form_conditions.all()
    }
    if projection.forms:
        lines += ["", "## Form packet"]
        for slug in projection.forms:
            form = forms[slug]
            lines.append(f"- {cited(source_marker(flow, slug), form.name)}")

    pages = [
        (page, components[f"interview-{number}"])
        for number, page in enumerate(flow.interview_pages.all(), 1)
        if f"interview-{number}" in components
    ]
    if pages:
        lines += ["", "## Facts the guided interview collects"]
        for page, component in pages:
            if page.title:
                lines += ["", f"### {page.title}"]
            if page.description:
                lines.append(page.description.strip())
            lines += [
                _variable_line(placement.variable)
                for placement in page.variables.all()
                if placement.variable.name in component.variables
            ]

    links = list(flow.links.all())
    if links:
        lines += ["", "## Links"]
        lines += [
            f"- {cited(source_marker(flow, link.key), link.name)}: {link.url}"
            for link in links
        ]

    progress = projection.model_dump(
        mode="json", exclude={"flow_id", "components", "forms", "deadlines"}
    )
    progress["components"] = [
        {"id": component.id, "complete": component.complete}
        for component in projection.components
    ]
    lines += ["", "## Current flow progress", json.dumps(progress)]
    return "\n".join(lines)


class LoadTopicFlow(Tool):
    """
    Load a guided topic flow and make it this conversation's active flow.

    Call this as soon as the user's situation matches one of the available
    topic flows listed in your instructions. Selecting a flow refreshes
    the current flow context with its applicable guidance, facts, forms,
    deadlines, and next components. Ground your answers in that context.
    Each block of guidance carries a [source:ID] marker for citations.
    """

    topic_flow: str = Field(
        description=(
            "The path of the flow to load: just the topic-slug/flow-slug "
            "that starts its line in your instructions, e.g. "
            "'eviction/tenant', with nothing after it"
        )
    )

    def __call__(self, *, thread_id) -> ToolOutput:
        from litigant_portal.app.selectors.topic_flow import topic_flow_list
        from litigant_portal.app.services.chat_engine import (
            chat_thread_state_merge,
        )

        flow = topic_flow_from_path(self.topic_flow, graph=False)
        if flow is None:
            available = (
                ", ".join(topic_flow_path(f) for f in topic_flow_list())
                or "none"
            )
            return ToolOutput(
                result=(
                    f"Error: no topic flow named '{self.topic_flow}'. "
                    f"Available flows: {available}."
                )
            )

        chat_thread_state_merge(
            thread_id=thread_id,
            updates={"active_topic_flow": topic_flow_path(flow)},
        )

        return ToolOutput(
            result=(
                f"The active topic flow is now {topic_flow_path(flow)} "
                f"({flow.name}). Use the refreshed current flow context."
            ),
            refresh_system_prompt=True,
            render_data={
                "topic_flow": topic_flow_path(flow),
                "name": flow.name,
                "topic": flow.topic.title,
            },
        )
