import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Now
from django.utils import formats, timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.translation import gettext_lazy as _

from litigant_portal.app.formatting import format_long_date

from .base import BaseModel
from .choices import TopicFlowFormConditionOperator, VariableDataType
from .shared import Attribution

SNAKE_CASE_PATTERN = r"^[a-z][a-z0-9_]*$"


class Topic(BaseModel):
    """A legal topic the app supports."""

    objects = models.Manager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=64, unique=True)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    icon = models.CharField(max_length=64, blank=True)
    meta_description = models.TextField(blank=True)
    prompts = models.JSONField(default=list, blank=True)
    order = models.PositiveIntegerField(default=0)

    enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "created_at"]


class TopicFlow(Attribution, BaseModel):
    """A guided flow for a topic."""

    objects = models.Manager()

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

    court_topic = models.ForeignKey(
        "CourtTopic", null=True, blank=True, on_delete=models.PROTECT
    )
    version = models.PositiveIntegerField(default=1)
    previous_version = models.OneToOneField(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="next_version",
    )
    guidance = models.TextField(blank=True)
    metadata = models.JSONField(default=dict)
    state = models.CharField(max_length=16, default="draft")

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["court_topic", "slug", "version"],
                name="topic_flow_court_slug_version",
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
    """
    A versioned definition of a fact about the person or their case.
    """

    objects = models.Manager()

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(
        max_length=255,
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
    in_schema = models.BooleanField(default=True)
    asked_when = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="gated_variables",
    )
    asked_when_value = models.JSONField(null=True, blank=True)

    version = models.PositiveIntegerField(default=1)
    value_schema = models.JSONField(default=dict)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "version"], name="variable_name_version"
            ),
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

    objects = models.Manager()

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

    matter = models.ForeignKey(
        "Matter", null=True, blank=True, on_delete=models.PROTECT
    )
    evidence_kind = models.CharField(max_length=32, default="user_statement")
    confirmation_state = models.CharField(max_length=16, default="unconfirmed")
    state = models.CharField(max_length=16, default="active")
    observed_at = models.DateTimeField(default=timezone.now, db_default=Now())
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    supersedes = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    invalidated_at = models.DateTimeField(null=True, blank=True)

    @property
    def display_value(self) -> str:
        """The stored value rendered for reading.

        ``value`` is jsonb, so a multi-choice answer arrives as a list, a
        boolean as a bool, and a date as an ISO string. Handing any of those
        straight to a template shows the litigant a Python repr or a raw
        `2026-09-09`, so the shaping lives here rather than in the template.
        """
        if isinstance(self.value, bool):
            return _("Yes") if self.value else _("No")
        if isinstance(self.value, list):
            return ", ".join(str(item) for item in self.value)
        if self.value is None:
            return ""
        return self._formatted_date() or str(self.value)

    def _formatted_date(self) -> str | None:
        """Long-form date for a date or datetime variable.

        None when the variable isn't temporal, isn't reachable, or the stored
        value doesn't parse — an unparseable date still has to render as
        whatever is stored rather than disappear.
        """
        try:
            data_type = self.variable.data_type
        except ObjectDoesNotExist:
            return None

        raw = str(self.value)
        if data_type == VariableDataType.DATE:
            parsed = parse_date(raw)
            # Same shape the flow page's deadlines use, so a litigant sees one
            # date format across both surfaces.
            return format_long_date(parsed) if parsed else None
        if data_type == VariableDataType.DATETIME:
            parsed = parse_datetime(raw)
            if parsed is None:
                return None
            return formats.date_format(parsed, "DATETIME_FORMAT")
        return None

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["identity", "matter", "variable"],
                condition=models.Q(
                    reviewed=True, state="active", invalidated_at__isnull=True
                ),
                nulls_distinct=False,
                name="answer_current_reviewed",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(reviewed=True, confirmation_state="confirmed")
                    | (
                        models.Q(reviewed=False)
                        & ~models.Q(confirmation_state="confirmed")
                    )
                ),
                name="answer_review_confirmation",
            ),
        ]


class Form(BaseModel):
    """A fillable PDF as a shared asset, belonging to no flow."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to="forms/")

    document = models.ForeignKey(
        "Document", null=True, blank=True, on_delete=models.PROTECT
    )

    class Meta:
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
    checked_when = models.ForeignKey(
        Variable,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="checkbox_fields",
    )
    checked_when_value = models.JSONField(null=True, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(checked_when__isnull=False)
                    | models.Q(checked_when_value__isnull=True)
                ),
                name="formfield_condition_value_requires_condition",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(checked_when__isnull=True)
                    | models.Q(checked_when_value__isnull=False)
                ),
                name="formfield_condition_requires_value",
            ),
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

    key = models.CharField(max_length=128, blank=True)
    instructions = models.TextField(blank=True)
    completion_criteria = models.JSONField(default=list)

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

    required = models.BooleanField(default=False)
    condition = models.JSONField(null=True, blank=True)

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

    page = models.ForeignKey(
        "TopicFlowInterviewPage",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="deadlines",
    )

    class Meta:
        ordering = ["order", "created_at"]
