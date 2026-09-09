"""
Shared model scripts and environment builders without host dependencies.
"""

from lp_agent.adapters.bedrock import MODEL_CHOICES
from lp_agent.adapters.catalog import Court
from lp_agent.adapters.memory import MemoryConversationStore, MemoryRunStore
from lp_agent.environment import AgentEnvironment, ScopedEnvironment
from lp_agent.types import (
    AccessContext,
    Choice,
    ModelMessage,
    ModelOutputItem,
    OutputText,
    ScopeSelection,
)


def answer_item(text):
    return ModelOutputItem(
        item=ModelMessage(
            role="assistant",
            content=(OutputText(text=text),),
            status="completed",
        )
    )


class ScriptedModel:
    """
    A core-only test model; no provider credentials or framework required.
    """

    def __init__(self, events):
        self.events = events
        self.requests = []
        self.closed = False

    async def stream(self, request):
        self.requests.append(request)
        try:
            for event in self.events:
                if isinstance(event, Exception):
                    raise event
                yield event
        finally:
            self.closed = True


class TestScopes:
    """
    Supply fixed authorized scope and a controlled model to the executor.
    """

    def __init__(self, model):
        self.model = model
        self.bindings = []

    async def courts(self, *, access, topic=None):
        return (Choice(choice_id="court", label="Court"),)

    async def topics(self, *, access, court):
        return (Choice(choice_id="topic", label="Topic"),)

    async def bind(self, *, access, scope):
        self.bindings.append(scope)
        return ScopedEnvironment(
            access=access,
            scope=scope,
            model=self.model,
            corpus=None,
            documents=None,
        )


def environment_for(model):
    conversations = MemoryConversationStore()
    scopes = TestScopes(model)
    return AgentEnvironment(
        access=AccessContext(identity_id="user-1"),
        scope=ScopeSelection(court="court", topic="topic"),
        conversations=conversations,
        runs=MemoryRunStore(conversations),
        catalog=scopes,
        scope_factory=scopes,
    )


def environment_options():
    return {
        "identity_id": "identity-1",
        "court": "court",
        "topic": "topic",
        "model": MODEL_CHOICES[0][0],
        "api_key": "test-only-key",
        "catalog": (
            Court(
                choice_id="court",
                label="Court",
                topics=(Choice(choice_id="topic", label="Topic"),),
            ),
        ),
    }
