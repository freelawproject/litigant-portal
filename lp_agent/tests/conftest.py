import pytest

from lp_agent import AgentIdentity
from lp_agent.types import AccessContext, ScopeSelection


class UnusedService:
    """
    Fail if a contract placeholder attempts any adapter work.
    """

    def __getattr__(self, name):
        raise AssertionError(
            f"Validation must not invoke service method {name}"
        )


@pytest.fixture
def environment():
    service = UnusedService()
    return AgentIdentity(
        access=AccessContext(identity_id="test-identity"),
        scope=ScopeSelection(court="court", topic="topic"),
        conversations=service,
        runs=service,
        scope_factory=service,
    )
