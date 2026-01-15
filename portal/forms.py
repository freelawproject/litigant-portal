from django import forms

from .models import UserProfile


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
                    "placeholder": "Your full legal name",
                    "autocomplete": "name",
                }
            ),
            "phone": forms.TextInput(
                attrs={
                    "placeholder": "(555) 123-4567",
                    "autocomplete": "tel",
                    "type": "tel",
                }
            ),
            "address_line1": forms.TextInput(
                attrs={
                    "placeholder": "123 Main Street",
                    "autocomplete": "address-line1",
                }
            ),
            "address_line2": forms.TextInput(
                attrs={
                    "placeholder": "Apartment, suite, unit, etc.",
                    "autocomplete": "address-line2",
                }
            ),
            "city": forms.TextInput(
                attrs={
                    "placeholder": "City",
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
                    "placeholder": "12345",
                    "autocomplete": "postal-code",
                }
            ),
            "county": forms.TextInput(
                attrs={
                    "placeholder": "e.g., Los Angeles County",
                }
            ),
        }
