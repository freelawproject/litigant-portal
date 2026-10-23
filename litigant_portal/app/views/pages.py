import os
from urllib.parse import urlsplit

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseNotAllowed,
)
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import DetailView, UpdateView

from litigant_portal.app.features import features
from litigant_portal.app.forms import UserProfileForm
from litigant_portal.app.models import UserProfile
from litigant_portal.app.models.choices import (
    DEFAULT_BEDROCK_MODEL,
    DEFAULT_FAST_BEDROCK_MODEL,
    BedrockModel,
    JurisdictionLevel,
    State,
)
from litigant_portal.app.selectors.site import contact_help_list, site_get
from litigant_portal.app.selectors.topic_flow import topic_list
from litigant_portal.app.services.user import user_identity_reset
from litigant_portal.app.views.utils import admin_tabs, briefcase_answers


# The Atomic Design summary page frames the real home page as its "page"
# column, so home opts in to same-origin framing (Django's default is DENY).
@xframe_options_sameorigin
def home(request):
    """Home page - dashboard with hero and topic grid."""
    topics = {t.slug: t for t in topic_list()}
    return render(
        request,
        "pages/home.html",
        {"topics": topics, "briefcase_groups": briefcase_answers(request)},
    )


def chat_view(request):
    """Chat page.

    The briefcase renders server-side from the visitor's stored facts, so the
    panel is populated on first paint rather than waiting on a fetch. The key
    is always present, empty list included — the panel is a fixed part of the
    frame and its empty state is a render, not an absence.
    """
    return render(
        request,
        "pages/chat/index.html",
        {"briefcase_groups": briefcase_answers(request)},
    )


def start_over(request):
    """Tester tool: start the session over from the seeded defaults
    (#969). On wherever ``features().start_over`` is (#1037).

    Deletes the visitor's chats, uploads and answers, then returns to
    the path of ``next`` when it is on this site. The query is dropped
    because ``/chat/?q=`` re-sends its question on load, which would start a
    new thread right after the reset. The site menu asks for confirmation
    first. Where the feature is off, this answers 404 whatever the menu
    shows, so the check lives on the server and not only in the template.
    """
    # Before the method check, so every method 404s where it's off and none
    # gives away that the endpoint exists.
    if not features().start_over:
        raise Http404
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    user_identity_reset(identity=request.identity)
    messages.success(
        request, _("Started over. Your chats and answers are cleared.")
    )
    next_url = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("pages:home")
    return redirect(urlsplit(next_url).path)


def about(request):
    """About page - mission, disclaimers, FLP info."""
    return render(request, "pages/about.html")


def privacy(request):
    """Privacy page - data practices and user rights."""
    return render(request, "pages/privacy.html")


def get_help(request):
    """Get help (#1022): the court's own details and the contacts its corpus
    marks with a help kind. Only what the corpus knows, so a court with no
    legal-aid contact shows no legal-aid line."""
    return render(
        request,
        "pages/help.html",
        {"site": site_get(), "help_contacts": contact_help_list()},
    )


def accessibility(request):
    """Accessibility page - WCAG conformance and feedback."""
    return render(request, "pages/accessibility.html")


class ProfileDetailView(LoginRequiredMixin, DetailView):
    """Display user's profile information."""

    model = UserProfile
    template_name = "pages/profile/detail.html"
    context_object_name = "profile"

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile


class ProfileEditView(LoginRequiredMixin, UpdateView):
    """Edit user profile."""

    model = UserProfile
    form_class = UserProfileForm
    template_name = "pages/profile/edit.html"
    success_url = reverse_lazy("pages:profile")

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def form_valid(self, form):
        messages.success(self.request, _("Profile updated successfully."))
        return super().form_valid(form)


@login_required
def admin(request: HttpRequest) -> HttpResponse:
    """Admin dashboard shell. Its tabs come from ``admin_tabs`` in the
    context processor, so a court admin gets the Users tab alone."""
    if not admin_tabs(request.user):
        raise PermissionDenied
    return render(
        request,
        "pages/admin/index.html",
        {
            "bedrock_available": bool(
                os.environ.get("AWS_BEARER_TOKEN_BEDROCK")
            ),
            "model_choices": BedrockModel.choices,
            "default_model_label": DEFAULT_BEDROCK_MODEL.label,
            "default_fast_model_label": DEFAULT_FAST_BEDROCK_MODEL.label,
            "jurisdiction_choices": JurisdictionLevel.choices,
            "state_choices": State.choices,
        },
    )
