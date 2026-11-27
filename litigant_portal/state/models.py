import uuid

from django.core.validators import RegexValidator
from django.db import models

from litigant_portal.app.models.base import BaseModel
from litigant_portal.state.rules import (
    condition_matches,
    parse_condition,
)
from litigant_portal.state.types import ConditionType

SNAKE_CASE_PATTERN = r"^[a-z][a-z0-9_]*$"


class VariableDataType(models.TextChoices):
    TEXT = "text", "Text"
    DATE = "date", "Date"
    DATETIME = "datetime", "Datetime"
    NUMBER = "number", "Number"
    CHOICE = "choice", "Choice"
    BOOLEAN = "boolean", "Boolean"


class Topic(BaseModel):
    """A legal topic the app supports."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=64, unique=True)
    court = models.SlugField(max_length=64, blank=True, default="")
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    icon = models.CharField(max_length=64, blank=True)
    meta_description = models.TextField(blank=True)
    prompts = models.JSONField(default=list, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "app"
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
    layout = models.JSONField(default=list, blank=True)
    interview_reference = models.CharField(max_length=255, blank=True)
    interview_prefill = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "app"
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
    key = models.SlugField(max_length=64, blank=True, default="")
    heading = models.CharField(max_length=255)
    content = models.TextField(blank=True)
    when = models.JSONField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "app"
        ordering = ["order", "created_at"]


class FlowViewState(BaseModel):
    """
    Viewed component signatures, separate from an identity's case facts.
    """

    identity = models.ForeignKey(
        "UserIdentity", on_delete=models.CASCADE, related_name="flow_views"
    )
    flow = models.ForeignKey(TopicFlow, on_delete=models.CASCADE)
    viewed = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "app"
        constraints = [
            models.UniqueConstraint(
                fields=["identity", "flow"], name="unique_identity_flow_view"
            )
        ]


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
    default = models.JSONField(null=True, blank=True)
    is_global = models.BooleanField(default=False)
    is_private = models.BooleanField(default=False)
    in_schema = models.BooleanField(default=True)
    asked_when = models.JSONField(null=True, blank=True)

    class Meta:
        app_label = "app"
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(name__regex=SNAKE_CASE_PATTERN),
                name="variable_name_snake_case",
            ),
        ]

    @property
    def condition(self) -> ConditionType | None:
        return parse_condition(self.asked_when)

    def is_asked(self, answers: dict) -> bool:
        """
        Whether this question applies to the current applicable answers.
        """
        return condition_matches(self.condition, answers)


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
    evidence = models.JSONField(null=True, blank=True)

    class Meta:
        app_label = "app"
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
    url = models.URLField(max_length=500, blank=True)

    class Meta:
        app_label = "app"
        ordering = ["slug"]


class FormField(BaseModel):
    """One AcroForm blank on a PDF: a template fills a text field, and
    ``checked``/``checked_when`` turn on a checkbox."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey(
        Form,
        on_delete=models.CASCADE,
        related_name="fields",
    )
    pdf_field = models.CharField(max_length=255)
    template = models.TextField(blank=True)
    checked = models.BooleanField(null=True, blank=True)
    checked_when = models.JSONField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "app"
        ordering = ["order", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(checked__isnull=True)
                    | models.Q(checked_when__isnull=True)
                ),
                name="formfield_checked_or_condition",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(template="")
                    | (
                        models.Q(checked__isnull=True)
                        & models.Q(checked_when__isnull=True)
                    )
                ),
                name="formfield_checkbox_takes_no_template",
            ),
            models.UniqueConstraint(
                fields=["form", "pdf_field"],
                name="formfield_pdf_field_unique_per_form",
            ),
        ]


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
    when = models.JSONField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "app"
        ordering = ["order", "created_at"]


class TopicFlowInterviewPage(BaseModel):
    """
    A question group whose applicability is computed from stored facts.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        TopicFlow,
        on_delete=models.CASCADE,
        related_name="interview_pages",
    )
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    when = models.JSONField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "app"
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
        app_label = "app"
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
    key = models.SlugField(max_length=64, blank=True, default="")
    name = models.CharField(max_length=255)
    url = models.URLField(max_length=500)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "app"
        ordering = ["order", "created_at"]


class TopicFlowDeadline(BaseModel):
    """A deadline computed relative to a variable's answer."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    flow = models.ForeignKey(
        TopicFlow,
        on_delete=models.CASCADE,
        related_name="deadlines",
    )
    key = models.SlugField(max_length=64, blank=True, default="")
    label = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    when = models.JSONField(null=True, blank=True)
    offset_days = models.IntegerField(default=0)
    offset_from = models.ForeignKey(
        Variable,
        on_delete=models.PROTECT,
        related_name="deadlines",
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = "app"
        ordering = ["order", "created_at"]

    @property
    def ref(self) -> str:
        """The authored key, or the row id for a row that has none."""
        return self.key or str(self.pk)
