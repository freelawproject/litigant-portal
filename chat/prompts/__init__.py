"""System prompt composition for the litigant assistant.

Prompts compose in four layers: Base + Phase + Topic + Court. See
`docs/prompts-as-infra.md` for the architectural principle and
`docs/nd-name-change-planning-log.md` for the patterns that drove the
decomposition.

- **Base** (always present): tone, UPL, conversation style, universal
  patterns (inform-first, what-before-why, escalation ladder, blockers,
  don't-make-user-re-enter, end-goal threading, consistent identity
  handling, scope-adjacent info-not-advice).
- **Phase** (always present): triage / prepare / resolve flow conventions.
  Session state determines current phase.
- **Topic** (optional): topic-specific legal framing — eviction concepts,
  adult name change concepts, etc. Court-agnostic.
- **Court** (optional): jurisdictional content — statutes, forms, fees,
  courthouse details, handoff referrals.

When real RAG / agentic tooling lands, Topic and Court shrink to retrieval
calls; Base and Phase stay. The composition interface does not change.
"""

from chat.prompts.base import BASE_PROMPT

# Lazy-loaded registries, keyed by phase / topic / court slug.
_PHASE_PROMPTS: dict[str, str] = {}
_TOPIC_PROMPTS: dict[str, str] = {}
_COURT_PROMPTS: dict[str, str] = {}
_COURT_NAMES: dict[str, str] = {}

# Backward-compat: old callers passed jurisdiction (two-letter state code).
# Map known states to their default court. Additional mappings land here as
# more courts are added.
_JURISDICTION_TO_COURT: dict[str, str] = {
    "il": "dupage_il",
    "nd": "nd",
}

_VALID_PHASES = ("triage", "prepare", "resolve")


def _load_phase_prompts() -> None:
    """Lazy-load phase prompt modules into the registry."""
    if _PHASE_PROMPTS:
        return
    from chat.prompts.phases.prepare import PROMPT as prepare
    from chat.prompts.phases.resolve import PROMPT as resolve
    from chat.prompts.phases.triage import PROMPT as triage

    _PHASE_PROMPTS["triage"] = triage
    _PHASE_PROMPTS["prepare"] = prepare
    _PHASE_PROMPTS["resolve"] = resolve


def _load_topic_prompts() -> None:
    """Lazy-load topic prompt modules into the registry."""
    if _TOPIC_PROMPTS:
        return
    from chat.prompts.topics.adult_name_change import (
        PROMPT as adult_name_change,
    )
    from chat.prompts.topics.eviction import PROMPT as eviction

    _TOPIC_PROMPTS["eviction"] = eviction
    _TOPIC_PROMPTS["adult_name_change"] = adult_name_change


def _load_court_prompts() -> None:
    """Lazy-load court prompt modules into the registry."""
    if _COURT_PROMPTS:
        return
    from chat.prompts.courts.dupage_il import PROMPT as dupage_il
    from chat.prompts.courts.nd import PROMPT as nd

    _COURT_PROMPTS["dupage_il"] = dupage_il
    _COURT_PROMPTS["nd"] = nd


def _load_court_names() -> None:
    """Lazy-load court display names into the registry."""
    if _COURT_NAMES:
        return
    from chat.prompts.courts.dupage_il import COURT_NAME as dupage_il_name
    from chat.prompts.courts.nd import COURT_NAME as nd_name

    _COURT_NAMES["dupage_il"] = dupage_il_name
    _COURT_NAMES["nd"] = nd_name


def get_court_name(court: str | None) -> str:
    """Return the human-readable display name for a court slug.

    Empty string for unknown or missing slugs — callers should treat empty
    as "no court branding" and omit the UI slot entirely.
    """
    if not court:
        return ""
    _load_court_names()
    return _COURT_NAMES.get(court.lower(), "")


def build_system_prompt(
    phase: str = "triage",
    topic: str | None = None,
    court: str | None = None,
    jurisdiction: str | None = None,
) -> str:
    """Compose the system prompt from Base + Phase + optional Topic + Court.

    Args:
        phase: Flow phase — "triage", "prepare", or "resolve". Defaults to
            "triage" so callers that haven't adopted the new signature yet
            get the right starting behavior.
        topic: Legal topic slug (e.g. "eviction", "adult_name_change"). None
            omits the topic layer.
        court: Court slug (e.g. "dupage_il", "nd"). None omits the court
            layer.
        jurisdiction: Deprecated — backward-compat for callers passing a
            two-letter state code. Maps to a default court via
            ``_JURISDICTION_TO_COURT``. Prefer ``court`` for new code.

    Returns:
        The assembled system prompt string.
    """
    if phase not in _VALID_PHASES:
        raise ValueError(
            f"Unknown phase {phase!r}. Expected one of {_VALID_PHASES}."
        )

    # Backward-compat: map jurisdiction → court if court not provided.
    if jurisdiction and not court:
        court = _JURISDICTION_TO_COURT.get(jurisdiction.lower())

    sections = [BASE_PROMPT]

    _load_phase_prompts()
    sections.append(_PHASE_PROMPTS[phase])

    if topic:
        _load_topic_prompts()
        topic_prompt = _TOPIC_PROMPTS.get(topic.lower())
        if topic_prompt:
            sections.append(topic_prompt)

    if court:
        _load_court_prompts()
        court_prompt = _COURT_PROMPTS.get(court.lower())
        if court_prompt:
            sections.append(court_prompt)

    return "\n\n".join(sections)


def phase_for_session(session) -> str:
    """Infer the current flow phase from a ChatSession's state.

    Simple initial implementation — returns "triage" for sessions without a
    resolution or substantive case facts, "prepare" once the case is
    identified and action items exist, "resolve" once a resolution has been
    recorded. Designed to be refined as session state richness grows.

    Args:
        session: ChatSession instance (or duck-typed equivalent with
            ``case_info`` and ``resolution`` attributes).

    Returns:
        One of "triage", "prepare", "resolve".
    """
    if session is None:
        return "triage"

    resolution = getattr(session, "resolution", None)
    if resolution:
        return "resolve"

    case_info = getattr(session, "case_info", None)
    if case_info:
        return "prepare"

    return "triage"
