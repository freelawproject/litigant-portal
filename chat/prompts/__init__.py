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

## Storage layout

Each Court and Topic lives in its own directory beneath this module:

    chat/prompts/
      courts/
        <slug>/
          court.json    # identity: name (more fields land with #363/#365)
          prompt.md     # corpus content
      topics/
        <slug>/
          prompt.md     # corpus content
          (topic.json lands with #363 — card display data)

Markdown lets non-engineer contributors edit corpus content via PR. The
per-court directory matches the eventual wiki tree (#355) so when AI-team
ingestion + retrieval lands, today's `prompt.md` files become the seed
corpus and `court.json` becomes the structured identity record. Base and
Phase stay as `.py` because they encode cross-cutting infrastructure, not
per-court content.

When real RAG / agentic tooling lands, Topic and Court shrink to retrieval
calls; Base and Phase stay. The composition interface does not change.
"""

import json
import logging
import re
from pathlib import Path

from chat.prompts.base import BASE_PROMPT

logger = logging.getLogger(__name__)

_PROMPTS_DIR = Path(__file__).parent

# Slug shape — alphanumeric, underscore, hyphen. Validated at the public
# boundary so path-traversal slugs (`..`, `/`) can never reach the
# filesystem layer.
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

# Lazy-loaded registries, keyed by phase / topic / court slug.
_PHASE_PROMPTS: dict[str, str] = {}
_TOPIC_PROMPTS: dict[str, str] = {}
_COURT_PROMPTS: dict[str, str] = {}
_COURT_META: dict[str, dict] = {}

# Backward-compat: old callers passed jurisdiction (two-letter state code).
# Map known states to their default court. Additional mappings land here as
# more courts are added.
_JURISDICTION_TO_COURT: dict[str, str] = {
    "il": "dupage_il",
    "nd": "nd",
}

_VALID_PHASES = ("triage", "prepare", "resolve")


def _safe_slug(slug: str | None) -> str | None:
    """Return the lowercased slug if it matches the safe shape, else None."""
    if not slug:
        return None
    lowered = slug.lower()
    if not _SLUG_RE.fullmatch(lowered):
        return None
    return lowered


def _read_prompt(category: str, slug: str) -> str | None:
    """Read `<category>/<slug>/prompt.md`. Returns None if missing."""
    path = _PROMPTS_DIR / category / slug / "prompt.md"
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def _read_court_meta(slug: str) -> dict | None:
    """Read `courts/<slug>/court.json`. Returns None if missing or unparseable.

    Missing files return silently — a court may legitimately have no
    metadata yet. Parse errors log a warning so deploy-time bugs surface in
    logs while branding falls back gracefully to "no court" rather than
    crashing the request.
    """
    path = _PROMPTS_DIR / "courts" / slug / "court.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse court metadata at %s: %s", path, exc)
        return None


def is_known_topic(slug: str | None) -> bool:
    """True iff a topic prompt is registered for the slug."""
    safe = _safe_slug(slug)
    if safe is None:
        return False
    return (_PROMPTS_DIR / "topics" / safe / "prompt.md").is_file()


def is_known_court(slug: str | None) -> bool:
    """True iff a court prompt is registered for the slug."""
    safe = _safe_slug(slug)
    if safe is None:
        return False
    return (_PROMPTS_DIR / "courts" / safe / "prompt.md").is_file()


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


def get_court_name(court: str | None) -> str:
    """Return the human-readable display name for a court slug.

    Empty string for unknown or missing slugs — callers should treat empty
    as "no court branding" and omit the UI slot entirely.
    """
    safe = _safe_slug(court)
    if safe is None:
        return ""
    if safe not in _COURT_META:
        meta = _read_court_meta(safe)
        if meta is not None:
            _COURT_META[safe] = meta
    return _COURT_META.get(safe, {}).get("name", "")


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
            or unrecognized slugs omit the topic layer silently.
        court: Court slug (e.g. "dupage_il", "nd"). None or unrecognized
            slugs omit the court layer silently.
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

    topic_slug = _safe_slug(topic)
    if topic_slug:
        if topic_slug not in _TOPIC_PROMPTS:
            content = _read_prompt("topics", topic_slug)
            if content is not None:
                _TOPIC_PROMPTS[topic_slug] = content
        topic_prompt = _TOPIC_PROMPTS.get(topic_slug)
        if topic_prompt:
            sections.append(topic_prompt)

    court_slug = _safe_slug(court)
    if court_slug:
        if court_slug not in _COURT_PROMPTS:
            content = _read_prompt("courts", court_slug)
            if content is not None:
                _COURT_PROMPTS[court_slug] = content
        court_prompt = _COURT_PROMPTS.get(court_slug)
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
