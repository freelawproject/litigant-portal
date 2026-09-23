"""
Shared court, matter, document, and attribution records.
"""

import uuid
from typing import TYPE_CHECKING

from django.db import models
from django.db.models.functions import Now
from django.utils import timezone

from .choices import JurisdictionLevel, State


class Record(models.Model):
    """
    Database defaults also support the existing SQL writer.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        db_default=models.Func(
            function="gen_random_uuid", output_field=models.UUIDField()
        ),
    )
    created_at = models.DateTimeField(auto_now_add=True, db_default=Now())
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())
    objects = models.Manager()

    class Meta:
        abstract = True


class ImportAudit(Record):
    """
    Provenance for an import, with a real initiating identity when available.
    """

    invocation_type = models.CharField(max_length=32)
    code_version = models.CharField(max_length=64)
    initiated_by = models.ForeignKey(
        "UserIdentity", null=True, blank=True, on_delete=models.PROTECT
    )

    class Meta:
        db_table = "app_import_audit"


class Attribution(models.Model):
    """
    A real human author or an explicit import source for each revision.
    """

    created_by = models.ForeignKey(
        "UserIdentity",
        db_column="created_by",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    reviewed_by = models.ForeignKey(
        "UserIdentity",
        db_column="reviewed_by",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    published_by = models.ForeignKey(
        "UserIdentity",
        db_column="published_by",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    import_audit = models.ForeignKey(
        ImportAudit,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True


class Court(Record):
    """
    Court records in the shared schema.
    """

    if TYPE_CHECKING:
        # Django supplies these methods for fields with choices.
        def get_state_display(self) -> str: ...
        def get_jurisdiction_level_display(self) -> str: ...

    slug = models.TextField()
    name = models.TextField()
    config = models.JSONField(default=dict, db_default={})
    enabled = models.BooleanField(default=True, db_default=True)
    court_name = models.CharField(
        max_length=255, blank=True, default="", db_default=""
    )
    jurisdiction_level = models.CharField(
        max_length=16,
        choices=JurisdictionLevel.choices,
        blank=True,
        default="",
        db_default="",
    )
    state = models.CharField(
        max_length=2,
        choices=State.choices,
        blank=True,
        default="",
        db_default="",
    )
    official_url = models.URLField(blank=True, default="", db_default="")
    official_resources_url = models.URLField(
        blank=True, default="", db_default=""
    )

    class Meta:
        db_table = "app_court"
        constraints = [
            models.UniqueConstraint(
                fields=["slug"], name="app_court_unique_0"
            ),
        ]


class CourtTopic(Record):
    """
    CourtTopic records in the shared schema.
    """

    court = models.ForeignKey(
        "Court", on_delete=models.PROTECT, related_name="+"
    )
    topic = models.ForeignKey(
        "Topic", on_delete=models.PROTECT, related_name="+"
    )
    config = models.JSONField(default=dict, db_default={})
    enabled = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "app_court_topic"
        constraints = [
            models.UniqueConstraint(
                fields=["court", "topic"], name="app_court_topic_unique_0"
            ),
            models.UniqueConstraint(
                fields=["id", "court", "topic"],
                name="app_court_topic_unique_1",
            ),
        ]


class Matter(Record):
    """
    Matter records in the shared schema.
    """

    user = models.ForeignKey(
        "UserIdentity",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="identity_id",
    )
    court_topic = models.ForeignKey(
        "CourtTopic", on_delete=models.PROTECT, related_name="+"
    )
    title = models.TextField()
    case_reference = models.TextField(null=True, blank=True)
    state = models.TextField(default="open", db_default="open")
    closed_at = models.DateTimeField(null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_matter"
        constraints = [
            models.UniqueConstraint(
                fields=["id", "user", "court_topic"],
                name="app_matter_unique_0",
            ),
            models.UniqueConstraint(
                fields=["id", "user"], name="app_matter_unique_1"
            ),
        ]


class PhaseDocument(Record):
    """
    PhaseDocument records in the shared schema.
    """

    phase = models.ForeignKey(
        "TopicFlowInterviewPage",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="page_id",
    )
    document = models.ForeignKey(
        "Document", on_delete=models.PROTECT, related_name="+"
    )
    purpose = models.TextField()
    position = models.IntegerField()
    condition = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "app_phase_document"
        constraints = [
            models.UniqueConstraint(
                fields=["phase", "document", "purpose"],
                name="app_phase_document_unique_0",
            ),
            models.UniqueConstraint(
                fields=["phase", "position"],
                name="app_phase_document_unique_1",
            ),
        ]


class Document(Attribution, Record):
    """
    Document records in the shared schema.
    """

    owner_kind = models.TextField()
    owner_court = models.ForeignKey(
        "Court",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    owner_user = models.ForeignKey(
        "UserIdentity",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    key = models.TextField()
    title = models.TextField()
    category = models.TextField()
    previous_version = models.ForeignKey(
        "Document",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    deleted_at = models.DateTimeField(null=True, blank=True)
    version = models.IntegerField()
    s3_bucket = models.TextField()
    s3_key = models.TextField()
    s3_object_version = models.TextField(null=True, blank=True)
    sha256 = models.TextField()
    byte_size = models.BigIntegerField()
    media_type = models.TextField()
    original_filename = models.TextField(null=True, blank=True)
    origin_url = models.TextField(null=True, blank=True)
    metadata = models.JSONField(default=dict, db_default={})
    state = models.TextField()
    storage_state = models.TextField(
        default="available", db_default="available"
    )
    index_revision = models.IntegerField(default=0, db_default=0)
    index_state = models.TextField(default="pending", db_default="pending")
    parser_version = models.TextField(null=True, blank=True)
    chunker_version = models.TextField(null=True, blank=True)
    index_config = models.JSONField(default=dict, db_default={})
    extraction_ref = models.JSONField(null=True, blank=True)
    embedding_provider = models.TextField(null=True, blank=True)
    embedding_model = models.TextField(null=True, blank=True)
    embedding_dimensions = models.IntegerField(null=True, blank=True)
    embedding_config = models.JSONField(default=dict, db_default={})
    chunk_count = models.IntegerField(default=0, db_default=0)
    indexed_at = models.DateTimeField(null=True, blank=True)
    index_error_code = models.TextField(null=True, blank=True)
    index_invalidated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_document"
        constraints = [
            models.UniqueConstraint(
                fields=["previous_version"], name="app_document_unique_0"
            ),
            models.UniqueConstraint(
                fields=[
                    "owner_kind",
                    "owner_court",
                    "owner_user",
                    "key",
                    "version",
                ],
                name="app_document_unique_1",
                nulls_distinct=False,
            ),
            models.UniqueConstraint(
                fields=["s3_bucket", "s3_key", "s3_object_version"],
                name="app_document_unique_2",
                nulls_distinct=False,
            ),
        ]


class CorpusDocument(Record):
    """
    CorpusDocument records in the shared schema.
    """

    court_topic = models.ForeignKey(
        "CourtTopic", on_delete=models.PROTECT, related_name="+"
    )
    document = models.ForeignKey(
        "Document", on_delete=models.PROTECT, related_name="+"
    )
    enabled = models.BooleanField(default=True, db_default=True)

    class Meta:
        db_table = "app_corpus_document"
        constraints = [
            models.UniqueConstraint(
                fields=["court_topic", "document"],
                name="app_corpus_document_unique_0",
            ),
        ]


class MatterDocument(Record):
    """
    MatterDocument records in the shared schema.
    """

    matter = models.ForeignKey(
        "Matter", on_delete=models.PROTECT, related_name="+"
    )
    document = models.ForeignKey(
        "Document", on_delete=models.PROTECT, related_name="+"
    )
    note = models.TextField(default="", db_default="")

    class Meta:
        db_table = "app_matter_document"
        constraints = [
            models.UniqueConstraint(
                fields=["matter", "document"],
                name="app_matter_document_unique_0",
            ),
        ]


class DocumentChunk(Record):
    """
    DocumentChunk records in the shared schema.
    """

    document = models.ForeignKey(
        "Document", on_delete=models.PROTECT, related_name="+"
    )
    ordinal = models.IntegerField()
    body = models.TextField()
    locator = models.JSONField()
    text_sha256 = models.TextField()

    class Meta:
        db_table = "app_document_chunk"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "ordinal"],
                name="app_document_chunk_unique_0",
            ),
        ]


class FactEvidence(Record):
    """
    FactEvidence records in the shared schema.
    """

    fact_assertion = models.ForeignKey(
        "VariableAnswer",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="answer_id",
    )
    role = models.TextField()
    conversation_item = models.ForeignKey(
        "ChatMessage",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        db_column="message_id",
    )
    document = models.ForeignKey(
        "Document",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    run_step = models.ForeignKey(
        "AgentRunStep",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    locator = models.JSONField(default=dict, db_default={})
    locator_sha256 = models.TextField()
    submitted_by = models.ForeignKey(
        "UserIdentity",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    class Meta:
        db_table = "app_fact_evidence"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "fact_assertion",
                    "role",
                    "conversation_item",
                    "document",
                    "run_step",
                    "locator_sha256",
                ],
                name="app_fact_evidence_unique_0",
                nulls_distinct=False,
            ),
        ]


class MatterProcedure(Record):
    """
    MatterProcedure records in the shared schema.
    """

    matter = models.ForeignKey(
        "Matter", on_delete=models.PROTECT, related_name="+"
    )
    procedure = models.ForeignKey(
        "TopicFlow",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="flow_id",
    )
    state = models.TextField(default="active", db_default="active")
    started_at = models.DateTimeField(default=timezone.now, db_default=Now())
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_matter_procedure"
        constraints = [
            models.UniqueConstraint(
                fields=["matter", "procedure"],
                name="app_matter_procedure_unique_0",
            ),
        ]


class PhaseProgress(Record):
    """
    PhaseProgress records in the shared schema.
    """

    matter_procedure = models.ForeignKey(
        "MatterProcedure", on_delete=models.PROTECT, related_name="+"
    )
    phase = models.ForeignKey(
        "TopicFlowInterviewPage",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="page_id",
    )
    state = models.TextField(default="not_started", db_default="not_started")
    basis = models.JSONField(default=dict, db_default={})
    last_run_step = models.ForeignKey(
        "AgentRunStep",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "app_phase_progress"
        constraints = [
            models.UniqueConstraint(
                fields=["matter_procedure", "phase"],
                name="app_phase_progress_unique_0",
            ),
        ]


class MessageAttachment(Record):
    """
    MessageAttachment records in the shared schema.
    """

    conversation_item = models.ForeignKey(
        "ChatMessage",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="message_id",
    )
    document = models.ForeignKey(
        "Document", on_delete=models.PROTECT, related_name="+"
    )
    position = models.IntegerField()

    class Meta:
        db_table = "app_message_attachment"
        constraints = [
            models.UniqueConstraint(
                fields=["conversation_item", "document"],
                name="app_message_attachment_unique_0",
            ),
            models.UniqueConstraint(
                fields=["conversation_item", "position"],
                name="app_message_attachment_unique_1",
            ),
        ]
