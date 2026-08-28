import json

from litigant_portal.agents.base import Field, Tool, ToolOutput


def topic_flow_path(flow) -> str:
    """The slug path that names ``flow`` in agent state and tool calls."""
    return f"{flow.topic.slug}/{flow.slug}"


def topic_flow_from_path(path: str):
    """The enabled TopicFlow at ``path`` (topic-slug/flow-slug), or None."""
    from litigant_portal.app.selectors.topic_flow import topic_flow_find

    topic_slug, sep, flow_slug = path.partition("/")
    if not (sep and topic_slug and flow_slug):
        return None
    return topic_flow_find(topic_slug=topic_slug, flow_slug=flow_slug)


def _variable_line(variable) -> str:
    line = f"- {variable.name} ({variable.data_type})"
    prompt = variable.question or variable.label
    if prompt:
        line += f": {prompt}"
    if variable.choices:
        values = ", ".join(c["value"] for c in variable.choices)
        line += f" [choices: {values}]"
    if variable.asked_when:
        line += (
            f" (asked when {variable.asked_when.name} = "
            f"{json.dumps(variable.asked_when_value)})"
        )
    return line


def topic_flow_markdown(flow) -> str:
    """Everything the assistant should know about ``flow``, as markdown."""
    lines = [f"# {flow.name}", f"Topic: {flow.topic.title}"]

    for section in flow.sections.all():
        lines += ["", f"## {section.heading}", section.content.strip()]

    deadlines = list(flow.deadlines.all())
    if deadlines:
        lines += ["", "## Deadlines"]
        for d in deadlines:
            anchor = d.offset_from.label or d.offset_from.name
            when = (
                f"{d.offset_days} days after"
                if d.offset_days >= 0
                else f"{-d.offset_days} days before"
            )
            line = f"- {d.label}: {when} {anchor}"
            if d.description:
                line += f". {d.description}"
            lines.append(line)

    conditions = list(flow.form_conditions.all())
    if conditions:
        lines += ["", "## Form packet"]
        for c in conditions:
            line = f"- {c.form.name}"
            if c.variable:
                line += (
                    f" (included when {c.variable.name} {c.operator} "
                    f"{json.dumps(c.value)})"
                )
            lines.append(line)

    pages = list(flow.interview_pages.all())
    if pages:
        lines += ["", "## Facts the guided interview collects"]
        for page in pages:
            if page.title:
                lines += ["", f"### {page.title}"]
            if page.description:
                lines.append(page.description.strip())
            lines += [
                _variable_line(pv.variable) for pv in page.variables.all()
            ]

    links = list(flow.links.all())
    if links:
        lines += ["", "## Links"]
        lines += [f"- {link.name}: {link.url}" for link in links]

    return "\n".join(lines)


class LoadTopicFlow(Tool):
    """Load a guided topic flow and make it this conversation's active flow.

    Call this as soon as the user's situation matches one of the available
    topic flows listed in your instructions. The result contains the flow's
    full content (its guidance, deadlines, forms, and the facts it
    collects); ground your answers in that content while the flow is
    active.
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

        flow = topic_flow_from_path(self.topic_flow)
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
                f"({flow.name}).\n\n{topic_flow_markdown(flow)}"
            ),
            render_data={
                "topic_flow": topic_flow_path(flow),
                "name": flow.name,
                "topic": flow.topic.title,
            },
        )
