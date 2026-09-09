import pytest

from lp_agent import AgentEnvironment
from lp_agent.types import AccessContext


class UnusedService:
    """
    Fail if a contract placeholder attempts any adapter work.
    """

    def __getattr__(self, name):
        raise AssertionError(f"PR1 must not invoke service method {name}")


@pytest.fixture
def environment():
    service = UnusedService()
    return AgentEnvironment(
        access=AccessContext(identity_id="test-identity"),
        conversations=service,
        runs=service,
        catalog=service,
        scope_factory=service,
    )
