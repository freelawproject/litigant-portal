import logging
import smtplib

from allauth.account.forms import ResetPasswordForm
from django import forms
from django.utils.translation import gettext_lazy as _

from .models import UserProfile

logger = logging.getLogger(__name__)


class PublicResetPasswordForm(ResetPasswordForm):
    """The "Forgot your password?" form. A failed send answers like a
    sent one, so the page never tells which addresses have an account."""

    def save(self, request, **kwargs) -> str:
        try:
            return super().save(request, **kwargs)
        except (smtplib.SMTPException, OSError):
            logger.exception("Could not send a password reset email")
            return self.cleaned_data["email"]


class UserProfileForm(forms.ModelForm):
    """Form for creating/updating user profiles."""

    class Meta:
        model = UserProfile
        fields = [
            "name",
            "phone",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "zip_code",
            "county",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "placeholder": _("Your full legal name"),
                    "autocomplete": "name",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "placeholder": _("(555) 123-4567"),
                    "autocomplete": "tel",
                    "type": "tel",
                }
            ),
            "address_line1": forms.TextInput(
                attrs={
                    "placeholder": _("123 Main Street"),
                    "autocomplete": "address-line1",
                }
            ),
            "address_line2": forms.TextInput(
                attrs={
                    "placeholder": _("Apartment, suite, unit, etc."),
                    "autocomplete": "address-line2",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "placeholder": _("City"),
                    "autocomplete": "address-level2",
                }
            ),
            "state": forms.Select(
                attrs={
                    "autocomplete": "address-level1",
                }
            ),
            "zip_code": forms.TextInput(
                attrs={
                    "placeholder": _("12345"),
                    "autocomplete": "postal-code",
                }
            ),
            "county": forms.TextInput(
                attrs={
                    "placeholder": _("e.g., Los Angeles County"),
                }
            ),
        }
