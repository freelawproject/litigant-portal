from django.db import transaction

from .base import Agent, AgentState
from .tools.load_topic_flow import LoadTopicFlow, topic_flow_path
from .tools.query_document import QueryDocument

BASE_PROMPT = """\
You are a compassionate legal assistant helping self-represented litigants \
understand their situation and navigate the legal system. You are embodying \
the knowledge of experienced attorneys and court self-help professionals.

The user can attach files (documents and images) to their messages. Small \
files appear directly in the conversation. A note reading [Attached file \
...] means the file is available but not shown — use the query_document \
tool with its upload_id to read or query it. Never guess at the contents \
of a file you haven't seen."""

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

PROMPT_TEMPLATE = """\
{base}

{topic_flows}"""


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


class LitigantAssistantState(AgentState):
    """Litigant assistant state."""

    active_topic_flow: str | None = None


class LitigantAssistant(Agent):
    """The user-facing assistant for self-represented litigants."""

    state_schema = LitigantAssistantState
    tools = [QueryDocument, LoadTopicFlow]

    def prepare_thread(self, *, thread_id) -> None:
        """Clear the thread's active topic flow when it no longer names an
        enabled flow.

        State stores a slug path, not a foreign key, so the flow may have
        been renamed, disabled, or deleted since it was set. The engine
        runs this once per user message, so a stale path never survives
        into a turn.
        """
        from litigant_portal.app.models import ChatThread
        from litigant_portal.app.selectors.topic_flow import topic_flow_list

        with transaction.atomic():
            thread = ChatThread.objects.select_for_update().get(id=thread_id)
            active = (thread.state or {}).get("active_topic_flow")
            if active and active not in {
                topic_flow_path(f) for f in topic_flow_list()
            }:
                thread.state = {**thread.state, "active_topic_flow": None}
                thread.save(update_fields=["state", "updated_at"])

    def generate_system_prompt(self, *, thread_id) -> str:
        """Each prompt piece injected into PROMPT_TEMPLATE."""
        return PROMPT_TEMPLATE.format(
            base=BASE_PROMPT,
            topic_flows=generate_topic_flows_prompt(),
        ).strip()
