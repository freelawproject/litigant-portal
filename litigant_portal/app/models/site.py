import uuid
from typing import TYPE_CHECKING

from django.db import models

from .base import BaseModel
from .choices import BedrockModel

if TYPE_CHECKING:
    from .shared import Court

SITE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class Site(BaseModel):
    """Site-wide settings. Constrained to a single row."""

    id = models.UUIDField(primary_key=True, default=SITE_ID, editable=False)
    if TYPE_CHECKING:
        court: Court | None
        court_id: uuid.UUID | None
    else:
        court = models.ForeignKey(
            "Court", null=True, blank=True, on_delete=models.PROTECT
        )
    fast_model = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        choices=BedrockModel.choices,
    )
    assistant_model = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        choices=BedrockModel.choices,
    )

    @property
    def court_name(self):
        """
        Retain the site's existing court metadata interface.
        """
        return self.court.court_name if self.court is not None else ""

    @property
    def jurisdiction_level(self):
        """
        Retain the site's existing court metadata interface.
        """
        return self.court.jurisdiction_level if self.court is not None else ""

    @property
    def state(self):
        """
        Retain the site's existing court metadata interface.
        """
        return self.court.state if self.court is not None else ""

    @property
    def official_url(self):
        """
        Retain the site's existing court metadata interface.
        """
        return self.court.official_url if self.court is not None else ""

    @property
    def official_resources_url(self):
        """
        Retain the site's existing court metadata interface.
        """
        return (
            self.court.official_resources_url if self.court is not None else ""
        )

    def get_state_display(self):
        """
        Display the court choice through the existing site interface.
        """
        return self.court.get_state_display() if self.court is not None else ""

    def get_jurisdiction_level_display(self):
        """
        Display the court choice through the existing site interface.
        """
        return (
            self.court.get_jurisdiction_level_display()
            if self.court is not None
            else ""
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


class Contact(BaseModel):
    """A court or legal-help contact."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    url = models.URLField(max_length=500, blank=True)
    note = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]


class Resource(BaseModel):
    """An external resource link."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=255, unique=True)
    url = models.URLField(max_length=500)
    note = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
