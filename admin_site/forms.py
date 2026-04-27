from django import forms
from django.utils.translation import gettext_lazy as _

from .models import ChatModel, Site


class SiteForm(forms.ModelForm):
    class Meta:
        model = Site
        fields = ["court_name", "chat_model"]
        widgets = {
            "court_name": forms.TextInput(
                attrs={"placeholder": _("e.g., Stanislaus County Superior Court")}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["chat_model"].empty_label = _("Disabled — chat is off")
        self.fields["chat_model"].queryset = ChatModel.objects.order_by("name")


class ChatModelForm(forms.ModelForm):
    class Meta:
        model = ChatModel
        fields = ["name", "slug"]
        widgets = {
            "name": forms.TextInput(
                attrs={"placeholder": _("e.g., GPT-4o mini")}
            ),
            "slug": forms.TextInput(
                attrs={"placeholder": _("e.g., openai/gpt-4o-mini")}
            ),
        }
        help_texts = {
            "slug": _(
                "LiteLLM model identifier passed to the chat provider."
            ),
        }
