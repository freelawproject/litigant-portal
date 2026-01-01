import uuid

from django.conf import settings
from django.db import connection, models

# PostgreSQL-specific imports (optional for SQLite)
try:
    from django.contrib.postgres.indexes import GinIndex
    from django.contrib.postgres.search import SearchVectorField

    HAS_POSTGRES = connection.vendor == "postgresql"
except ImportError:
    HAS_POSTGRES = False
    GinIndex = None
    SearchVectorField = None


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
    """A message within a chat session."""

    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"
        SYSTEM = "system", "System"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        ChatSession,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    # Source references for RAG responses
    sources = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

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

    # Note: PostgreSQL full-text search (SearchVectorField + GinIndex)
    # will be added when RAG is implemented

    def __str__(self):
        return self.title
