import uuid

from django.db import models

from .base import BaseModel


class Topic(BaseModel):
    """A legal topic the app supports."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=64, unique=True)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    icon = models.CharField(max_length=64, blank=True)
    meta_description = models.TextField(blank=True)
    prompts = models.JSONField(default=list, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]


class TopicFlow(BaseModel):
    """A guided flow for a topic."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name="flows",
    )
    slug = models.SlugField(max_length=64)
    name = models.CharField(max_length=255)
    enabled = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["topic", "slug"], name="unique_topic_flow_slug"
            )
        ]


class TopicFlowSection(BaseModel):
    """A content section within a topic flow."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        TopicFlow,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    heading = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]


class TopicFlowFieldGroup(BaseModel):
    """A page of fields within a flow's interview."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        TopicFlow,
        on_delete=models.CASCADE,
        related_name="field_groups",
    )
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]


class TopicFlowField(BaseModel):
    """A question the interview asks, and the answer's shape."""

    class DataType(models.TextChoices):
        TEXT = "text", "Text"
        DATE = "date", "Date"
        DATETIME = "datetime", "Datetime"
        NUMBER = "number", "Number"
        CHOICE = "choice", "Choice"
        BOOLEAN = "boolean", "Boolean"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(
        TopicFlowFieldGroup,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    name = models.CharField(max_length=255)
    label = models.CharField(max_length=255, blank=True)
    help_text = models.TextField(blank=True)
    required = models.BooleanField(default=False)
    data_type = models.CharField(
        max_length=32, choices=DataType.choices, default=DataType.TEXT
    )
    choices = models.JSONField(default=list, blank=True)
    default = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["group", "order"],
                name="unique_group_field_order",
                deferrable=models.Deferrable.DEFERRED,
            )
        ]


class TopicFlowLink(BaseModel):
    """A link associated with a topic flow."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        TopicFlow,
        on_delete=models.CASCADE,
        related_name="links",
    )
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]


class TopicFlowDeadline(BaseModel):
    """A deadline computed relative to a topic flow field answer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        TopicFlow,
        on_delete=models.CASCADE,
        related_name="deadlines",
    )
    label = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    offset_days = models.IntegerField(default=0)
    offset_from = models.ForeignKey(
        TopicFlowField,
        on_delete=models.CASCADE,
        related_name="deadlines",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]


class TopicFlowForm(BaseModel):
    """A fillable PDF form attached to a topic flow."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        TopicFlow,
        on_delete=models.CASCADE,
        related_name="forms",
    )
    slug = models.SlugField(max_length=64)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to="flow_forms/")
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["flow", "slug"], name="unique_topic_flow_form_slug"
            )
        ]


class TopicFlowFormField(BaseModel):
    """A mapping from flow field answers onto one PDF form field."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey(
        TopicFlowForm,
        on_delete=models.CASCADE,
        related_name="mappings",
    )
    pdf_field = models.CharField(max_length=255)
    template = models.TextField(blank=True)
    checked_when = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]


class TopicFlowAnswer(BaseModel):
    """An identity's stored answer to a topic flow field."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.ForeignKey(
        "UserIdentity",
        on_delete=models.CASCADE,
        related_name="flow_answers",
    )
    field = models.ForeignKey(
        TopicFlowField,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    value = models.JSONField(null=True, blank=True)
    reviewed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["identity", "field"],
                name="unique_identity_flow_answer",
            )
        ]
