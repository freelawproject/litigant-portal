from litigant_portal.app.topic_flow.registry import registry

from .base import Agent
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

# Discovery #670: the least prompt possible to make the assistant aware the
# hard Topic Flow links exist. Iterate the wording here as chatting teaches us.
FLOW_PROMPT = """

The portal also offers guided step-by-step flows for specific situations. \
They are linked in the sidebar under "Guided steps":
{inventory}

When the user's situation matches one of these, point them to the matching \
sidebar link. The flows work without chat and let people move at their own \
pace."""


def flow_prompt_section() -> str:
    """Inventory of authored Topic Flow tracks, or empty when none exist."""
    tracks = registry.all_tracks()
    if not tracks:
        return ""
    inventory = "\n".join(f"- {track['title']}" for track in tracks)
    return FLOW_PROMPT.format(inventory=inventory)


class LitigantAssistant(Agent):
    """The user-facing assistant for self-represented litigants."""

    tools = [QueryDocument]

    def generate_system_prompt(self, *, thread_id) -> str:
        return BASE_PROMPT + flow_prompt_section()
