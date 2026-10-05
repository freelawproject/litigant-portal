import json

from .base import Agent, AgentState, IdentityPrompt
from .tools.load_topic_flow import LoadTopicFlow, topic_flow_path
from .tools.query_document import QueryDocument
from .tools.record_fact import RecordFact
from .tools.review_facts import ReviewFacts

BASE_PROMPT = """\
You are a compassionate legal assistant helping self-represented litigants \
understand their situation and navigate the legal system. You are embodying \
the knowledge of experienced attorneys and court self-help professionals.

The user can attach files (documents and images) to their messages. Small \
files appear directly in the conversation. A note reading [Attached file \
...] means the file is available but not shown — use the query_document \
tool with its upload_id to read or query it. Never guess at the contents \
of a file you haven't seen.

When the active topic flow's needed facts are all saved, or when the user \
asks to review their answers or to finish, call the ReviewFacts tool \
instead of listing their facts in prose."""

COURT_PROMPT = """\
## Court context

{context}"""

MULTI_COURT_CONTEXT = """\
This portal is running in multi-court mode: the guided topic flows may \
belong to different courts. Confirm which court and state the user's case \
is in before relying on court-specific details."""

FACTS_PROMPT = """\
## Facts the user has already provided

Never re-ask a fact listed here. Confirmed facts were reviewed by the \
user. Unconfirmed facts are the user's own statements awaiting their \
review: treat them as what the user told you, and when the user corrects \
one, save the new value with RecordFact. If a listed fact may not apply \
to the current matter, confirm it rather than re-ask it from scratch. \
Never invent a fact that is not listed here or stated by the user.

{facts}"""

TOPIC_FLOWS_PROMPT = """\
## Guided topic flows

The portal has guided topic flows: step-by-step guides for specific legal \
situations, with local court information, deadlines, and forms. As soon as \
the user's situation matches one, call the LoadTopicFlow tool with the \
flow's path (the topic-slug/flow-slug before the colon in the list \
below). The result names the conversation's active flow and gives you the \
flow's full content; treat that content as your primary source while the \
flow is active. Available flows:

{flows}"""


def _court_source_marker(key: str) -> str:
    from litigant_portal.app.selectors.corpus import COURT_SOURCE_SLUG

    return f"[source:{COURT_SOURCE_SLUG}/{key}]"


def _contact_line(contact) -> str:
    details = [
        f"{label} {value}"
        for label, value in (
            ("phone", contact.phone),
            ("email", contact.email),
            ("website", contact.url),
        )
        if value
    ]
    line = f"- {_court_source_marker(contact.key)} {contact.name}"
    if details:
        line += f" ({', '.join(details)})"
    if contact.note:
        line += f": {contact.note}"
    return line


def _resource_line(resource) -> str:
    line = f"- {_court_source_marker(resource.key)} {resource.label}: "
    line += resource.url
    if resource.note:
        line += f". {resource.note}"
    return line


def _court_sources() -> list[str]:
    """The court's contacts and resources, each with its citable id, so
    they can be cited before any flow is loaded. Empty lists render no
    heading."""
    from litigant_portal.app.selectors.site import contact_list, resource_list

    lines = []
    contacts = contact_list()
    if contacts:
        lines += ["", "### Court contacts"]
        lines += [_contact_line(c) for c in contacts]
    resources = resource_list()
    if resources:
        lines += ["", "### Court resources"]
        lines += [_resource_line(r) for r in resources]
    return lines


def generate_court_prompt() -> str:
    """The court-context section. A blank court name means the site
    wasn't synced to one court, so the flows may span several."""
    from litigant_portal.app.selectors.site import site_get

    site = site_get()
    if not site.court_name:
        lines = [MULTI_COURT_CONTEXT]
    else:
        lines = [f"You are operating in {site.court_name}."]
        if site.jurisdiction_level:
            level = site.get_jurisdiction_level_display()
            lines.append(f"- Jurisdiction level: {level}")
        if site.state:
            lines.append(f"- State: {site.get_state_display()}")
        if site.official_url:
            lines.append(f"- Court website: {site.official_url}")
        if site.official_resources_url:
            lines.append(
                f"- Court self-help resources: {site.official_resources_url}"
            )
    return COURT_PROMPT.format(context="\n".join(lines + _court_sources()))


def generate_topic_flows_prompt() -> str:
    """The guided-topic-flows section, or '' when no flows are enabled."""
    from litigant_portal.app.selectors.topic_flow import topic_flow_list

    flows = topic_flow_list()
    if not flows:
        return ""
    return TOPIC_FLOWS_PROMPT.format(
        flows="\n".join(
            f"- {topic_flow_path(f)}: {f.name} ({f.topic.title})"
            for f in flows
        )
    )


def _fact_values(answers) -> dict[str, str]:
    """Variable name -> the value exactly as the facts section renders it.

    json.dumps: a value with a newline must not add its own prompt lines.
    """
    return {
        a.variable.name: json.dumps(str(a.display_value), ensure_ascii=False)
        for a in answers
    }


def _facts_prompt(answers) -> str:
    values = _fact_values(answers)
    facts = "\n".join(
        f"- {a.variable.name} ({a.variable.label or a.variable.name}): "
        f"{values[a.variable.name]} "
        f"[{'confirmed' if a.reviewed else 'unconfirmed'}]"
        for a in answers
    )
    return FACTS_PROMPT.format(facts=facts)


class LitigantAssistantState(AgentState):
    """Litigant assistant state."""

    active_topic_flow: str | None = None


class LitigantAssistant(Agent):
    """The user-facing assistant for self-represented litigants."""

    state_schema = LitigantAssistantState
    tools = [QueryDocument, LoadTopicFlow, RecordFact, ReviewFacts]

    def prepare_thread(self, *, thread_id) -> None:
        """Clear the thread's active topic flow when it no longer names an
        enabled flow.

        State stores a slug path, not a foreign key, so the flow may have
        been renamed, disabled, or deleted since it was set. The engine
        runs this once per user message, so a stale path never survives
        into a turn.
        """
        from litigant_portal.app.selectors.topic_flow import topic_flow_list
        from litigant_portal.app.services.chat_engine import (
            chat_thread_state_merge,
        )

        def clear_if_stale(state: dict) -> dict:
            active = state.get("active_topic_flow")
            if active and active not in {
                topic_flow_path(f) for f in topic_flow_list()
            }:
                return {"active_topic_flow": None}
            return {}

        chat_thread_state_merge(thread_id=thread_id, updates=clear_if_stale)

    def generate_system_prompt(self, *, thread_id) -> str:
        """The non-empty shared prompt sections, blank-line separated.

        The active topic flow is deliberately absent: the model learns it
        from the LoadTopicFlow result in history, which only works while
        the engine sends the full history. When we add automatic compaction,
        we'll need to account for the active topic flow data being dropped from
        history.
        """
        return "\n\n".join(
            section
            for section in (
                BASE_PROMPT,
                generate_court_prompt(),
                generate_topic_flows_prompt(),
            )
            if section
        )

    def generate_identity_prompt(self, *, thread_id) -> IdentityPrompt | None:
        """The stored-facts section for the thread's identity, or None.

        RecordFact sets refresh_system_prompt when it saves, so a fact stored
        mid-turn appears here before the model's next step.
        """
        from litigant_portal.app.selectors.chat_engine import (
            chat_thread_identity_get,
        )
        from litigant_portal.app.selectors.topic_flow import (
            variable_answer_list,
        )

        identity = chat_thread_identity_get(thread_id=thread_id)
        answers = variable_answer_list(identity=identity, answered_only=True)
        if not answers:
            return None
        return IdentityPrompt(
            text=_facts_prompt(answers), values=_fact_values(answers)
        )
