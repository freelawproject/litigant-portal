"""
Read public conversation state and the enabled scope catalog for host interfaces.
"""

from lp_agent.adapters.session import DatabaseConnections
from lp_agent.errors import AgentAccessError
from lp_agent.preparation import CourtChoice
from lp_agent.types import AccessContext


async def scope_choices() -> tuple[CourtChoice, ...]:
    """
    Read the same database catalog used by static scope selection.
    """
    from lp_agent.adapters.db import AgentDatabase

    connections = DatabaseConnections()
    async with connections.connection() as connection:
        db = AgentDatabase(
            connection, AccessContext(identity_id="scope-catalog")
        )
        return await db.scope_choices(connections.court)


async def conversation_snapshot(
    access: AccessContext, conversation_id: str
) -> dict:
    """
    Return the owner's visible messages, safe run failures, and preparation state.
    """
    from lp_agent.adapters.db import AgentDatabase

    connections = DatabaseConnections()
    async with connections.connection() as connection:
        db = AgentDatabase(connection, access)
        async with db.transaction():
            await connection.execute(
                "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
            )
            conversation = await db.conversation(conversation_id)
            if connections.court and conversation["court"] not in (
                None,
                connections.court,
            ):
                raise AgentAccessError("Conversation is unavailable.")
            latest = await (
                await connection.execute(
                    "SELECT checkpoint_data, checkpoint_redacted_at FROM agent_run WHERE conversation_id = %s ORDER BY created_at DESC, id DESC LIMIT 1",
                    (conversation_id,),
                )
            ).fetchone()
            if latest and latest["checkpoint_redacted_at"] is not None:
                raise AgentAccessError("Conversation context is unavailable.")
            checkpoint = (latest["checkpoint_data"] or {}) if latest else {}
            rows = await (
                await connection.execute(
                    """
                SELECT i.id, i.run_id, i.payload, r.outcome
                FROM agent_conversation_item i LEFT JOIN agent_run r ON r.id = i.run_id
                WHERE i.conversation_id = %s AND i.visibility = 'user'
                    AND i.context_state = 'accepted' AND i.redacted_at IS NULL
                    AND i.item_kind = 'message'
                ORDER BY i.sequence
                """,
                    (conversation_id,),
                )
            ).fetchall()
            messages = []
            for row in rows:
                payload = row["payload"]
                role = payload.get("role")
                if role not in ("user", "assistant"):
                    continue
                content = payload.get("content", "")
                text = (
                    content
                    if isinstance(content, str)
                    else "".join(
                        part.get("text", part.get("refusal", ""))
                        for part in content
                        if part.get("type") in ("output_text", "refusal")
                    )
                )
                outcome = row["outcome"] or {}
                sources = (
                    outcome.get("sources", []) if role == "assistant" else []
                )
                messages.append(
                    {
                        "id": str(row["id"]),
                        "role": role,
                        "text": text,
                        "sources": sources,
                    }
                )
                if role == "user" and outcome.get("state") == "failed":
                    # Display the public failure without making it accepted model
                    # history or exposing any of the rejected candidate answers.
                    messages.append(
                        {
                            "id": f"failure:{row['run_id']}",
                            "role": "assistant",
                            "text": outcome["error"]["message"],
                            "sources": [],
                        }
                    )
            return {
                "conversation_id": conversation_id,
                "scope": {
                    "court": conversation["court"],
                    "topic": conversation["topic"],
                },
                "model": checkpoint.get("model_identifier"),
                "judge": checkpoint.get("judge_identifier"),
                "progress": checkpoint.get("progress", {}),
                "messages": messages,
            }
