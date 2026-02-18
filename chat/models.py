import uuid

from django.conf import settings
from django.db import models
from django_pydantic_field import SchemaField

from chat.agents.base import Message as MessageSchema


class ChatSession(models.Model):
    """A chat conversation session."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="chat_sessions",
    )
    # For anonymous users, track by session key
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["session_key", "-created_at"]),
        ]

    def __str__(self):
        if self.user:
            return f"Chat {self.id} - {self.user}"
        return f"Chat {self.id} - Anonymous"


class Message(models.Model):
    """A message within a chat session.

    The `data` field stores the full message dict, validated against the
    Message schema from chat.agents.base (SystemMessage, UserMessage,
    AssistantMessage, or ToolMessage).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ChatSession,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    data = SchemaField(
        schema=MessageSchema, default={"role": "system", "content": ""}
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

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


class Document(models.Model):
    """RAG document storage for domain knowledge (not yet implemented)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=500)
    content = models.TextField()
    source_url = models.URLField(blank=True)
    category = models.CharField(max_length=100, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
