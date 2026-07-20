import uuid

from django.conf import settings
from django.db import models

from .base import BaseModel
from .choices import JurisdictionLevel, State


class Site(BaseModel):
    """Site-wide settings. Exactly one row is `active` at a time."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    active = models.BooleanField(default=False)
    court_name = models.CharField(max_length=255, blank=True)
    jurisdiction_level = models.CharField(
        max_length=16, blank=True, choices=JurisdictionLevel.choices
    )
    state = models.CharField(max_length=2, blank=True, choices=State.choices)
    official_url = models.URLField(blank=True)
    official_resources_url = models.URLField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["active"],
                condition=models.Q(active=True),
                name="unique_active_site",
            )
        ]


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
