"""
Shared model scripts and environment builders without host dependencies.
"""

from pathlib import Path

from lp_agent.adapters.bedrock import MODEL_CHOICES
from lp_agent.adapters.memory import MemoryConversationStore, MemoryRunStore
from lp_agent.identity import AgentIdentity, ResourceScope
from lp_agent.types import (
    AccessContext,
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


class RecordingScopeFactory:
    """
    Record scope bindings and supply a controlled model to the executor.
    """

    def __init__(self, model):
        self.model = model
        self.bindings = []

    async def bind(self, *, access, scope):
        self.bindings.append(scope)
        return ResourceScope(
            access=access,
            scope=scope,
            model=self.model,
        )


def environment_for(model):
    conversations = MemoryConversationStore()
    scopes = RecordingScopeFactory(model)
    return AgentIdentity(
        access=AccessContext(identity_id="user-1"),
        scope=ScopeSelection(court="court", topic="topic"),
        conversations=conversations,
        runs=MemoryRunStore(conversations),
        scope_factory=scopes,
    )


def environment_options():
    return {
        "identity_id": "identity-1",
        "court": "court",
        "topic": "topic",
        "model": MODEL_CHOICES[0][0],
        "api_key": "test-only-key",
        "resource_root": Path("unused-corpus"),
    }
