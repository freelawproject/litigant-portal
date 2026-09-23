"""
Agent execution, instruction, and recall records.
"""

from django.db import models

from .shared import Attribution, Record


class AgentPrompt(Attribution, Record):
    """
    AgentPrompt records in the shared schema.
    """

    key = models.TextField()
    description = models.TextField(default="", db_default="")
    metadata = models.JSONField(default=dict, db_default={})
    previous_version = models.ForeignKey(
        "AgentPrompt",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    version = models.IntegerField()
    body = models.TextField()
    state = models.TextField(default="draft", db_default="draft")

    class Meta:
        db_table = "agent_prompt"
        constraints = [
            models.UniqueConstraint(
                fields=["previous_version"], name="agent_prompt_unique_0"
            ),
            models.UniqueConstraint(
                fields=["key", "version"], name="agent_prompt_unique_1"
            ),
        ]


class AgentMemory(Record):
    """
    AgentMemory records in the shared schema.
    """

    user = models.ForeignKey(
        "UserIdentity",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="identity_id",
    )
    matter = models.ForeignKey(
        "Matter",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    kind = models.TextField()
    body = models.TextField()
    state = models.TextField(default="active", db_default="active")
    conversation = models.ForeignKey(
        "ChatThread",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        db_column="thread_id",
    )
    first_sequence = models.BigIntegerField(null=True, blank=True)
    last_sequence = models.BigIntegerField(null=True, blank=True)
    generated_step = models.ForeignKey(
        "AgentRunStep", on_delete=models.PROTECT, related_name="+"
    )
    supersedes = models.ForeignKey(
        "AgentMemory",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    invalidated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agent_memory"


class AgentMemorySource(Record):
    """
    AgentMemorySource records in the shared schema.
    """

    memory = models.ForeignKey(
        "AgentMemory", on_delete=models.PROTECT, related_name="+"
    )
    conversation_item = models.ForeignKey(
        "ChatMessage",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        db_column="message_id",
    )
    fact_assertion = models.ForeignKey(
        "VariableAnswer",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        db_column="answer_id",
    )
    document = models.ForeignKey(
        "Document",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    locator = models.JSONField(default=dict, db_default={})
    locator_sha256 = models.TextField()

    class Meta:
        db_table = "agent_memory_source"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "memory",
                    "conversation_item",
                    "fact_assertion",
                    "document",
                    "locator_sha256",
                ],
                name="agent_memory_source_unique_0",
                nulls_distinct=False,
            ),
        ]


class AgentRun(Record):
    """
    AgentRun records in the shared schema.
    """

    conversation = models.ForeignKey(
        "ChatThread",
        on_delete=models.PROTECT,
        related_name="+",
        db_column="thread_id",
    )
    request = models.JSONField()
    configuration = models.JSONField()
    state = models.TextField(default="queued", db_default="queued")
    attempt = models.IntegerField(default=1, db_default=1)
    lock_version = models.BigIntegerField(default=0, db_default=0)
    pending_question = models.JSONField(null=True, blank=True)
    outcome = models.JSONField(null=True, blank=True)
    request_key = models.TextField()
    cancel_requested_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    context_court_topic = models.ForeignKey(
        "CourtTopic",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    context_format_version = models.IntegerField(null=True, blank=True)
    context_selected_at = models.DateTimeField(null=True, blank=True)
    resolved_config = models.JSONField(null=True, blank=True)
    manifest = models.JSONField(null=True, blank=True)
    recall_policy_snapshot = models.JSONField(null=True, blank=True)
    manifest_sha256 = models.TextField(null=True, blank=True)
    checkpoint_sequence = models.BigIntegerField(default=0, db_default=0)
    checkpoint_format_version = models.IntegerField(null=True, blank=True)
    checkpoint_attempt = models.IntegerField(null=True, blank=True)
    checkpoint_step = models.ForeignKey(
        "AgentRunStep",
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
    )
    checkpoint_conversation_sequence = models.BigIntegerField(
        null=True, blank=True
    )
    checkpoint_data = models.JSONField(null=True, blank=True)
    checkpoint_redacted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "agent_run"
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "request_key"],
                name="agent_run_unique_0",
            ),
            models.UniqueConstraint(
                fields=["id", "conversation"], name="agent_run_unique_1"
            ),
        ]


class AgentRunStep(Record):
    """
    AgentRunStep records in the shared schema.
    """

    run = models.ForeignKey(
        "AgentRun", on_delete=models.PROTECT, related_name="+"
    )
    attempt = models.IntegerField()
    sequence = models.IntegerField()
    kind = models.TextField()
    state = models.TextField(default="pending", db_default="pending")
    operation_key = models.TextField()
    input = models.JSONField()
    output = models.JSONField(null=True, blank=True)
    model_identifier = models.TextField(null=True, blank=True)
    tool_name = models.TextField(null=True, blank=True)
    tool_call_id = models.TextField(null=True, blank=True)
    usage = models.JSONField(default=dict, db_default={})
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    error_code = models.TextField(null=True, blank=True)
    redacted_at = models.DateTimeField(null=True, blank=True)
    prompt_artifact = models.ForeignKey(
        "PromptArtifact",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="agent_steps",
    )

    class Meta:
        db_table = "agent_run_step"
        constraints = [
            models.UniqueConstraint(
                fields=["run", "attempt", "sequence"],
                name="agent_run_step_unique_0",
            ),
            models.UniqueConstraint(
                fields=["run", "attempt", "operation_key"],
                name="agent_run_step_unique_1",
            ),
            models.UniqueConstraint(
                fields=["id", "run"], name="agent_run_step_unique_2"
            ),
        ]
