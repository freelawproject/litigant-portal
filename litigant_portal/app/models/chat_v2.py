import uuid

from django.db import models
from django_pydantic_field import SchemaField

from litigant_portal.agents.base import Message as MessageSchema

from .base import BaseModel


class ChatThread(BaseModel):
    """A chat conversation thread."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.ForeignKey(
        "UserIdentity",
        on_delete=models.CASCADE,
        related_name="chat_threads",
    )
    state = models.JSONField(default=dict, blank=True)


class ChatMessage(BaseModel):
    """A message within a chat thread."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    thread = models.ForeignKey(
        ChatThread,
        related_name="messages",
        on_delete=models.CASCADE,
    )
    data = SchemaField(
        schema=MessageSchema, default={"role": "system", "content": ""}
    )
    hidden = models.BooleanField(default=False)
