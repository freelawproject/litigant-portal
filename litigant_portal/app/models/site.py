import uuid

from django.conf import settings
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


class Contact(BaseModel):
    """A court or legal-help contact."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    url = models.URLField(max_length=500, blank=True)
    note = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)


class Resource(BaseModel):
    """An external resource link."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=255, unique=True)
    url = models.URLField(max_length=500)
    note = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)


class SiteMembership(BaseModel):
    """Grants a user admin access to one site's content."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="site_memberships",
    )
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="memberships",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "site"], name="unique_site_membership"
            )
        ]


class Topic(BaseModel):
    """A legal topic the app supports."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(
        Site,
        on_delete=models.CASCADE,
        related_name="topics",
    )
    slug = models.SlugField(max_length=64)
    title = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, blank=True)
    description = models.CharField(max_length=255, blank=True)
    icon = models.CharField(max_length=64, blank=True)
    meta_description = models.TextField(blank=True)
    prompts = models.JSONField(default=list, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["site", "slug"], name="unique_site_topic_slug"
            )
        ]
