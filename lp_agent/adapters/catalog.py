"""
A plain catalogue supplied by the host and bound to its verified identity.
"""

from typing import Self

from pydantic import model_validator

from lp_agent.errors import AgentAccessError, AgentValidationError
from lp_agent.types import AccessContext, Choice


class Court(Choice):
    """
    A permitted court and its permitted topic choices.
    """

    topics: tuple[Choice, ...]

    @model_validator(mode="after")
    def unique_topics(self) -> Self:
        ids = [topic.choice_id for topic in self.topics]
        if len(ids) != len(set(ids)):
            raise ValueError("topic IDs must be unique within a court")
        return self


class StaticScopeCatalog:
    """
    Serve a validated snapshot without framework queries during execution.
    """

    def __init__(self, access: AccessContext, courts: tuple[Court, ...]):
        self._access = access
        self._courts = courts
        if len({court.choice_id for court in courts}) != len(courts):
            raise AgentValidationError("court IDs must be unique")

    def _authorize(self, access: AccessContext) -> None:
        if access != self._access:
            raise AgentAccessError("Scope is unavailable to this identity.")

    async def courts(
        self, *, access: AccessContext, topic: str | None = None
    ) -> tuple[Choice, ...]:
        self._authorize(access)
        return tuple(
            Choice(choice_id=court.choice_id, label=court.label)
            for court in self._courts
            if topic is None or topic in {t.choice_id for t in court.topics}
        )

    async def topics(
        self, *, access: AccessContext, court: str
    ) -> tuple[Choice, ...]:
        self._authorize(access)
        return next(
            (item.topics for item in self._courts if item.choice_id == court),
            (),
        )
