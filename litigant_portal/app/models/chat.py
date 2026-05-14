from django.db import models
from django_pydantic_field import SchemaField

from litigant_portal.agents.base import Message
from litigant_portal.app.models.auth import UserIdentity

from .base import BaseModel


class ChatThread(BaseModel):
    uid = models.ForeignKey(UserIdentity, on_delete=models.CASCADE)
    agent_name = models.CharField(max_length=100, db_index=True)
    agent_state = models.JSONField(default=dict)
    forked_from = models.ForeignKey(
        "ChatMessage", on_delete=models.CASCADE, blank=True, null=True
    )

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["uid", "agent_name", "-updated_at"]),
        ]

    @property
    def history(self) -> list[Message]:
        """Get the thread's message history."""
        return [x.data for x in self.messages.order_by("created_at")]

    def __str__(self):
        return f"Chat {self.id} - {self.uid}"


class ChatMessage(BaseModel):
    thread = models.ForeignKey(
        ChatThread, on_delete=models.CASCADE, related_name="messages"
    )
    data = SchemaField(Message)
    compaction_checkpoint = models.BooleanField(default=False)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["thread", "-created_at"]),
        ]

    @property
    def role(self) -> str:
        """Get the message role from data."""
        return self.data.get("role", "")

    @property
    def content(self) -> str:
        """Get the message content from data."""
        return self.data.get("content", "")

    def __str__(self):
        preview = (
            self.content[:50] + "..."
            if len(self.content) > 50
            else self.content
        )
        return f"{self.role}: {preview}"
