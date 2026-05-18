from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class UserProfile(models.Model):
    """
    Extended profile data for authenticated users.

    OneToOne relationship with User model allows storing additional
    information without modifying AUTH_USER_MODEL.
    """

    STATE_CHOICES = [
        ("AL", _("Alabama")),
        ("AK", _("Alaska")),
        ("AZ", _("Arizona")),
        ("AR", _("Arkansas")),
        ("CA", _("California")),
        ("CO", _("Colorado")),
        ("CT", _("Connecticut")),
        ("DE", _("Delaware")),
        ("FL", _("Florida")),
        ("GA", _("Georgia")),
        ("HI", _("Hawaii")),
        ("ID", _("Idaho")),
        ("IL", _("Illinois")),
        ("IN", _("Indiana")),
        ("IA", _("Iowa")),
        ("KS", _("Kansas")),
        ("KY", _("Kentucky")),
        ("LA", _("Louisiana")),
        ("ME", _("Maine")),
        ("MD", _("Maryland")),
        ("MA", _("Massachusetts")),
        ("MI", _("Michigan")),
        ("MN", _("Minnesota")),
        ("MS", _("Mississippi")),
        ("MO", _("Missouri")),
        ("MT", _("Montana")),
        ("NE", _("Nebraska")),
        ("NV", _("Nevada")),
        ("NH", _("New Hampshire")),
        ("NJ", _("New Jersey")),
        ("NM", _("New Mexico")),
        ("NY", _("New York")),
        ("NC", _("North Carolina")),
        ("ND", _("North Dakota")),
        ("OH", _("Ohio")),
        ("OK", _("Oklahoma")),
        ("OR", _("Oregon")),
        ("PA", _("Pennsylvania")),
        ("RI", _("Rhode Island")),
        ("SC", _("South Carolina")),
        ("SD", _("South Dakota")),
        ("TN", _("Tennessee")),
        ("TX", _("Texas")),
        ("UT", _("Utah")),
        ("VT", _("Vermont")),
        ("VA", _("Virginia")),
        ("WA", _("Washington")),
        ("WV", _("West Virginia")),
        ("WI", _("Wisconsin")),
        ("WY", _("Wyoming")),
        ("DC", _("District of Columbia")),
    ]

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
    state = models.CharField(max_length=2, choices=STATE_CHOICES, blank=True)
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
