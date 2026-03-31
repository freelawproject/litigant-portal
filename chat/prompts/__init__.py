"""System prompt composition for the litigant assistant.

Prompts are split into a base layer (tone, conversation style, tools, UPL)
and optional topic/jurisdiction layers that add domain knowledge.  When real
RAG lands, the topic layers shrink and knowledge comes from API calls instead
— but the composition interface stays the same.
"""

from chat.prompts.base import BASE_PROMPT

# Registry: (topic, jurisdiction) -> module-level PROMPT string
_TOPIC_PROMPTS: dict[tuple[str, str], str] = {}


def _load_topic_prompts() -> None:
    """Lazy-load topic prompt modules into the registry."""
    if _TOPIC_PROMPTS:
        return
    from chat.prompts.eviction_il import PROMPT as eviction_il

    _TOPIC_PROMPTS[("eviction", "il")] = eviction_il


def build_system_prompt(
    topic: str | None = None,
    jurisdiction: str | None = None,
) -> str:
    """Compose the full system prompt from base + optional topic layer.

    Args:
        topic: Legal topic slug (e.g. "eviction"). None for generic.
        jurisdiction: Two-letter state code (e.g. "il"). None for generic.

    Returns:
        The assembled system prompt string.
    """
    sections = [BASE_PROMPT]

    if topic and jurisdiction:
        _load_topic_prompts()
        key = (topic.lower(), jurisdiction.lower())
        topic_prompt = _TOPIC_PROMPTS.get(key)
        if topic_prompt:
            sections.append(topic_prompt)

    return "\n\n".join(sections)
