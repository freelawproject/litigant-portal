"""
Authorization and snapshot ownership at the memory-store boundary.
"""

import asyncio

import pytest

from lp_agent import AgentAccessError, AgentValidationError
from lp_agent.adapters.memory import MemoryConversationStore, MemoryRunStore
from lp_agent.types import (
    AccessContext,
    AgentConfiguration,
    CompletedOutcome,
    RunCheckpoint,
    RunRequest,
    Scope,
    ScopeSelection,
)

ACCESS = AccessContext(identity_id="owner")
INTRUDER = AccessContext(identity_id="another-identity")


async def create_run():
    conversations = MemoryConversationStore()
    conversation = await conversations.create(
        access=ACCESS, scope=ScopeSelection(court="court", topic="topic")
    )
    runs = MemoryRunStore(conversations)
    status = await runs.create(
        access=ACCESS,
        conversation_id=conversation.conversation_id,
        request=RunRequest(message="Question"),
        configuration=AgentConfiguration(),
    )
    return runs, status


def test_run_reads_and_writes_enforce_identity():
    async def scenario():
        runs, status = await create_run()
        status = status.model_copy(update={"state": "completed"})
        reference = {
            "run_id": status.run_id,
            "conversation_id": status.conversation_id,
        }
        checkpoint = RunCheckpoint(**reference, data={"answer": "Done"})
        outcome = CompletedOutcome(**reference, text="Done")
        await runs.commit_checkpoint(
            access=ACCESS,
            checkpoint=checkpoint,
            status=status,
            outcome=outcome,
        )
        assert (
            await runs.outcome(access=ACCESS, run_id=status.run_id) == outcome
        )
        for read in (runs.status, runs.checkpoint, runs.outcome):
            with pytest.raises(AgentAccessError):
                await read(access=INTRUDER, run_id=status.run_id)
        with pytest.raises(AgentAccessError):
            await runs.commit_checkpoint(
                access=INTRUDER,
                checkpoint=checkpoint,
                status=status,
                outcome=outcome,
            )
        assert await runs.status(access=ACCESS, run_id=status.run_id) == status

    asyncio.run(scenario())


def test_checkpoints_are_copied_on_write_and_read():
    async def scenario():
        runs, status = await create_run()
        checkpoint = RunCheckpoint(
            run_id=status.run_id,
            conversation_id=status.conversation_id,
            data={"items": ["original"]},
        )
        await runs.commit_checkpoint(
            access=ACCESS, checkpoint=checkpoint, status=status
        )
        checkpoint.data["items"].append("changed after write")
        saved = await runs.checkpoint(access=ACCESS, run_id=status.run_id)
        assert saved.data == {"items": ["original"]}
        saved.data["items"].clear()
        reread = await runs.checkpoint(access=ACCESS, run_id=status.run_id)
        assert reread.data == {"items": ["original"]}

    asyncio.run(scenario())


@pytest.mark.parametrize("field", ["run_id", "conversation_id"])
def test_mismatched_checkpoint_does_not_change_saved_state(field):
    async def scenario():
        runs, status = await create_run()
        reference = {
            "run_id": status.run_id,
            "conversation_id": status.conversation_id,
        }
        checkpoint = RunCheckpoint(
            **(reference | {field: "another-record"}), data={}
        )
        with pytest.raises(
            AgentValidationError, match="references must match"
        ):
            await runs.commit_checkpoint(
                access=ACCESS, checkpoint=checkpoint, status=status
            )
        assert await runs.status(access=ACCESS, run_id=status.run_id) == status
        assert (
            await runs.checkpoint(access=ACCESS, run_id=status.run_id) is None
        )

    asyncio.run(scenario())


def test_conversation_binding_preserves_identity_and_selected_scope():
    async def scenario():
        conversations = MemoryConversationStore()
        conversation = await conversations.create(
            access=ACCESS, scope=ScopeSelection(court="court")
        )
        scope = Scope(court="court", topic="topic")
        with pytest.raises(AgentAccessError):
            await conversations.bind_scope(
                access=INTRUDER,
                conversation_id=conversation.conversation_id,
                scope=scope,
            )
        await conversations.bind_scope(
            access=ACCESS,
            conversation_id=conversation.conversation_id,
            scope=scope,
        )
        with pytest.raises(AgentAccessError, match="scope cannot change"):
            await conversations.bind_scope(
                access=ACCESS,
                conversation_id=conversation.conversation_id,
                scope=Scope(court="court", topic="another-topic"),
            )
        saved = await conversations.get(
            access=ACCESS, conversation_id=conversation.conversation_id
        )
        assert saved.scope == ScopeSelection(court="court", topic="topic")

    asyncio.run(scenario())
