import uuid

from django.core.validators import RegexValidator
from django.db import models

from .base import BaseModel
from .choices import TopicFlowFormConditionOperator, VariableDataType

SNAKE_CASE_PATTERN = r"^[a-z][a-z0-9_]*$"


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


class Variable(BaseModel):
    """A fact about the person or their case, named once app-wide."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255,
        unique=True,
        validators=[RegexValidator(SNAKE_CASE_PATTERN, "Use snake_case.")],
    )
    label = models.CharField(max_length=255, blank=True)
    question = models.CharField(max_length=255, blank=True)
    help_text = models.TextField(blank=True)
    required = models.BooleanField(default=False)
    data_type = models.CharField(
        max_length=32,
        choices=VariableDataType.choices,
        default=VariableDataType.TEXT,
    )
    choices = models.JSONField(default=list, blank=True)
    default = models.CharField(max_length=255, blank=True)
    is_global = models.BooleanField(default=False)
    asked_when = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gated_variables",
    )
    asked_when_value = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(name__regex=SNAKE_CASE_PATTERN),
                name="variable_name_snake_case",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(asked_when__isnull=False)
                    | models.Q(asked_when_value__isnull=True)
                ),
                name="variable_gate_value_requires_gate",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(asked_when__isnull=True)
                    | models.Q(asked_when_value__isnull=False)
                ),
                name="variable_gate_requires_value",
            ),
        ]


class VariableAnswer(BaseModel):
    """An identity's stored answer to a glossary variable."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.ForeignKey(
        "UserIdentity",
        on_delete=models.CASCADE,
        related_name="variable_answers",
    )
    variable = models.ForeignKey(
        Variable,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    value = models.JSONField(null=True, blank=True)
    reviewed = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["identity", "variable"],
                name="unique_identity_variable_answer",
            )
        ]


class Form(BaseModel):
    """A fillable PDF as a shared asset, belonging to no flow."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to="forms/")

    class Meta:
        ordering = ["slug"]


class FormField(BaseModel):
    """One AcroForm blank on a PDF, and the template that fills it."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey(
        Form,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    pdf_field = models.CharField(max_length=255)
    template = models.TextField(blank=True)
    checked_when = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]


class TopicFlowFormCondition(BaseModel):
    """Puts one form into one flow's packet, optionally on a condition."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        TopicFlow,
        on_delete=models.CASCADE,
        related_name="form_conditions",
    )
    form = models.ForeignKey(
        Form,
        on_delete=models.CASCADE,
        related_name="flow_conditions",
    )
    variable = models.ForeignKey(
        Variable,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="form_conditions",
    )
    operator = models.CharField(
        max_length=32,
        choices=TopicFlowFormConditionOperator.choices,
        default=TopicFlowFormConditionOperator.EQUALS,
    )
    value = models.JSONField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(variable__isnull=False)
                    | models.Q(value__isnull=True)
                ),
                name="form_condition_value_requires_variable",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(variable__isnull=True)
                    | models.Q(value__isnull=False)
                ),
                name="form_condition_variable_requires_value",
            ),
        ]


class TopicFlowInterviewPage(BaseModel):
    """A page of a flow's guided interview. Purely cosmetic grouping."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        TopicFlow,
        on_delete=models.CASCADE,
        related_name="interview_pages",
    )
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]


class TopicFlowInterviewVariable(BaseModel):
    """Places one glossary variable on one interview page."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey(
        TopicFlowInterviewPage,
        on_delete=models.CASCADE,
        related_name="variables",
    )
    variable = models.ForeignKey(
        Variable,
        on_delete=models.CASCADE,
        related_name="interview_placements",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["page", "variable"],
                name="unique_interview_page_variable",
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
    """A deadline computed relative to a variable's answer."""

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
        Variable,
        on_delete=models.PROTECT,
        related_name="deadlines",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
