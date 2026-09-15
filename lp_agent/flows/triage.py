"""
Static scope questions shared by persisted chat turns; no model is involved.
"""

from typing import Literal

from lp_agent.preparation import CourtChoice
from lp_agent.types import Choice, ScopeSelection


def scope_question(
    scope: ScopeSelection, courts: tuple[CourtChoice, ...]
) -> tuple[Literal["court", "topic"], tuple[Choice, ...]]:
    """
    Offer a court first, respecting an already supplied topic.
    """
    if scope.court is None:
        return "court", tuple(
            Choice(choice_id=court.choice_id, label=court.label)
            for court in courts
            if scope.topic is None
            or any(topic.choice_id == scope.topic for topic in court.topics)
        )
    return "topic", next(
        (court.topics for court in courts if court.choice_id == scope.court),
        (),
    )


def selected_choice(message: str, choices: tuple[Choice, ...]) -> str | None:
    """
    Accept only a displayed number, exact label, or exact identifier.
    """
    value = message.strip().casefold()
    matches = {
        choice.choice_id
        for number, choice in enumerate(choices, 1)
        if value
        in (str(number), choice.choice_id.casefold(), choice.label.casefold())
    }
    return next(iter(matches)) if len(matches) == 1 else None


def question_text(field: str, choices: tuple[Choice, ...]) -> str:
    """
    Render choices in the existing chat composer.
    """
    if not choices:
        return "There are no available court and topic options for this selection. Start a new conversation to choose another scope."
    return (
        f"Choose the {field} for your legal matter:\n\n"
        + "\n".join(
            f"{number}. {choice.label}"
            for number, choice in enumerate(choices, 1)
        )
        + "\n\nReply with the number or name. I’ll keep your original question while we select the court and topic."
    )
