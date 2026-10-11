import uuid

from django.core.files.storage import storages
from django.db import models

from .base import BaseModel
from .choices import BedrockModel, ContactKind, JurisdictionLevel, State

SITE_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _public_storage():
    """Court art is shown to every visitor, so it lives in public storage.
    A callable, so the storage choice stays out of migrations."""
    return storages["public"]


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
    # Written by sync_corpus from the court's branding block (#979).
    # branding_name, when set, replaces court_name in the header.
    branding_name = models.CharField(max_length=255, blank=True)
    logo = models.FileField(
        upload_to="branding/", storage=_public_storage, blank=True
    )
    name_image = models.FileField(
        upload_to="branding/", storage=_public_storage, blank=True
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
    key = models.SlugField(max_length=64, blank=True, default="")
    name = models.CharField(max_length=255, unique=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    url = models.URLField(max_length=500, blank=True)
    note = models.TextField(blank=True)
    # Blank for a contact the help page doesn't list (a bailiff's office,
    # a community group).
    kind = models.CharField(
        max_length=16, blank=True, choices=ContactKind.choices
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]


class Resource(BaseModel):
    """An external resource link."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    key = models.SlugField(max_length=64, blank=True, default="")
    label = models.CharField(max_length=255, unique=True)
    url = models.URLField(max_length=500)
    note = models.TextField(blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "created_at"]
