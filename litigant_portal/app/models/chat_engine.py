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
    matter = models.ForeignKey(
        "Matter", null=True, blank=True, on_delete=models.PROTECT
    )
    court_topic = models.ForeignKey(
        "CourtTopic", null=True, blank=True, on_delete=models.PROTECT
    )
    court = models.ForeignKey(
        "Court", null=True, blank=True, on_delete=models.PROTECT
    )
    topic = models.ForeignKey(
        "Topic", null=True, blank=True, on_delete=models.PROTECT
    )
    status = models.CharField(max_length=16, default="active")
    next_sequence = models.PositiveBigIntegerField(default=1)
    deleted_at = models.DateTimeField(null=True, blank=True)


class PromptArtifact(BaseModel):
    """The instruction state sent to the model for an assistant message."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    system_prompt = models.TextField()
    tool_schemas = models.JSONField(default=list, blank=True)
    content_hash = models.CharField(max_length=64, unique=True)
    canonical_format = models.CharField(max_length=64, blank=True)
    canonical_payload = models.TextField(blank=True)


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
    sequence = models.PositiveBigIntegerField(null=True, blank=True)
    deduplication_key = models.CharField(max_length=255, null=True, blank=True)
    item_kind = models.CharField(max_length=32, default="message")
    origin = models.CharField(max_length=16, default="framework")
    context_state = models.CharField(max_length=16, default="pending")
    search_text = models.TextField(null=True, blank=True)
    redacted_at = models.DateTimeField(null=True, blank=True)
    run = models.ForeignKey(
        "AgentRun",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    run_step = models.ForeignKey(
        "AgentRunStep",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
