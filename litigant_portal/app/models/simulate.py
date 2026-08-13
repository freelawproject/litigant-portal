import uuid

from django.db import models

from .base import BaseModel


class SimulatedUser(BaseModel):
    """A synthetic litigant persona for exercising the assistant.

    Each simulated user owns a real ``UserIdentity``, so everything the
    assistant does for a person — chat threads, uploads, topic flow
    answers — works unchanged for a simulation: the tools never know the
    identity isn't a live human. Deleting the identity cascades away the
    simulated user and all of that state.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.OneToOneField(
        "UserIdentity",
        on_delete=models.CASCADE,
        related_name="simulated_user",
    )
    name = models.CharField(max_length=255)
    # The persona: who they are, what happened, what they want. Feeds the
    # simulator agent's system prompt verbatim.
    story = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at"]
