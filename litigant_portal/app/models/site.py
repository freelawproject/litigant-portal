import uuid

from django.db import models

from .base import BaseModel
from .choices import AI_MODEL_CHOICES, JurisdictionLevel, State

SITE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class Site(BaseModel):
    """Site-wide settings. Constrained to a single row."""

    id = models.UUIDField(primary_key=True, default=SITE_ID, editable=False)
    court_name = models.CharField(max_length=255, blank=True)
    jurisdiction_level = models.CharField(
        max_length=16, blank=True, choices=JurisdictionLevel.choices
    )
    state = models.CharField(max_length=2, blank=True, choices=State.choices)
    official_url = models.URLField(blank=True)
    official_resources_url = models.URLField(blank=True)
    fast_model = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        choices=AI_MODEL_CHOICES,
    )
    assistant_model = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        choices=AI_MODEL_CHOICES,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(id=SITE_ID), name="single_site_row"
            )
        ]
        permissions = [
            ("manage_site", "Can manage the site"),
            ("manage_developers", "Can manage developer access"),
        ]
