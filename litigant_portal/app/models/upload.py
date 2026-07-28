import uuid

from django.db import models

from .base import BaseModel


def user_upload_path(instance, filename: str) -> str:
    """Upload S3 bucket path."""
    return f"uploads/{instance.id}/{filename}"


class UserUpload(BaseModel):
    """A file uploaded by a user, attachable to assistant messages."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identity = models.ForeignKey(
        "UserIdentity",
        on_delete=models.CASCADE,
        related_name="uploads",
    )
    file = models.FileField(upload_to=user_upload_path)
    name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField(default=0)
    pages = models.PositiveIntegerField(null=True, blank=True)
    text_chars = models.PositiveBigIntegerField(null=True, blank=True)
