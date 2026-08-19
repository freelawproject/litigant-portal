from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .base import BaseModel
from .choices import State


class UserIdentity(BaseModel):
    """Single identity row for either an authenticated user or an anonymous session."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="identity",
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)


class UserProfile(models.Model):
    """
    Extended profile data for authenticated users.

    OneToOne relationship with User model allows storing additional
    information without modifying AUTH_USER_MODEL.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    # Contact information
    name = models.CharField(
        max_length=255, blank=True, help_text=_("Full legal name")
    )
    phone = models.CharField(
        max_length=20, blank=True, help_text=_("Phone number")
    )

    # Address fields
    address_line1 = models.CharField(
        max_length=255, blank=True, verbose_name=_("Street address")
    )
    address_line2 = models.CharField(
        max_length=255, blank=True, verbose_name=_("Apt, suite, etc.")
    )
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, choices=State.choices, blank=True)
    zip_code = models.CharField(
        max_length=10, blank=True, verbose_name=_("ZIP code")
    )
    county = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("User Profile")
        verbose_name_plural = _("User Profiles")

    def __str__(self):
        return f"{self.name or 'Unnamed'} ({self.user.email})"

    @property
    def full_address(self):
        """Return formatted full address."""
        if not self.address_line1:
            return ""
        parts = [self.address_line1]
        if self.address_line2:
            parts.append(self.address_line2)
        if self.city and self.state:
            parts.append(f"{self.city}, {self.state} {self.zip_code}".strip())
        return "\n".join(parts)
