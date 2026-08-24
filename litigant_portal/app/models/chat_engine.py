import uuid

from django.db import models
from django_pydantic_field import SchemaField

from litigant_portal.agents.message_schema import MessageSchema

from .base import BaseModel


class ChatThread(BaseModel):
    """A chat conversation thread."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.ForeignKey(
        "UserIdentity",
        on_delete=models.CASCADE,
        related_name="chat_threads",
    )
    thread_type = models.CharField(
        max_length=50, db_index=True, default="user_chat"
    )
    state = models.JSONField(default=dict, blank=True)
    description = models.CharField(max_length=255, blank=True, default="")


class PromptArtifact(BaseModel):
    """The instruction state sent to the model for an assistant message."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    system_prompt = models.TextField()
    tool_schemas = models.JSONField(default=list, blank=True)
    content_hash = models.CharField(max_length=64, unique=True)


class ChatMessage(BaseModel):
    """A message within a chat thread."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        ChatThread,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    prompt_artifact = models.ForeignKey(
        PromptArtifact,
        related_name="chat_messages",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    data = SchemaField(
        schema=MessageSchema, default={"role": "system", "content": ""}
    )
    hidden = models.BooleanField(default=False)
    meta = models.BooleanField(default=False)
    num_tokens = models.PositiveIntegerField(default=0)
    cost = models.FloatField(default=0.0)
    git_sha = models.CharField(max_length=40, blank=True, default="")
