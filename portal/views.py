from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, UpdateView

from chat.agents import agent_registry

from .forms import UserProfileForm
from .models import UserProfile

TOPICS = {
    "housing": {
        "title": _("Housing & Eviction"),
        "subtitle": _(
            "Understanding the eviction process, tenant rights, and landlord obligations"
        ),
        "description": _("Landlord disputes, eviction defense, tenant rights"),
        "icon": "home",
        "meta_description": _(
            "Learn about the eviction process, tenant rights, and landlord obligations. General legal information for self-represented litigants."
        ),
    },
    "family": {
        "title": _("Family & Divorce"),
        "subtitle": _(
            "Divorce, custody, child support, and domestic violence resources"
        ),
        "description": _("Divorce, custody, child support, domestic issues"),
        "icon": "users",
        "meta_description": _(
            "Learn about divorce, child custody, child support, and family court. General legal information for self-represented litigants."
        ),
    },
    "small-claims": {
        "title": _("Small Claims"),
        "subtitle": _(
            "Resolving disputes and understanding the small claims court process"
        ),
        "description": _("Disputes under $10,000, debt collection defense"),
        "icon": "currency-dollar",
        "meta_description": _(
            "Learn about filing or defending a small claims case. General legal information for self-represented litigants."
        ),
    },
    "consumer": {
        "title": _("Consumer Rights"),
        "subtitle": _(
            "Debt collection rules, contract disputes, and consumer protections"
        ),
        "description": _("Scams, unfair business practices, contracts"),
        "icon": "shield-check",
        "meta_description": _(
            "Learn about consumer rights, debt collection rules, and contract disputes. General legal information for self-represented litigants."
        ),
    },
    "expungement": {
        "title": _("Expungement"),
        "subtitle": _(
            "Clearing or sealing your criminal record and restoring opportunities"
        ),
        "description": _("Clear your record, seal court files"),
        "icon": "document-text",
        "meta_description": _(
            "Learn about expungement, record sealing, and eligibility requirements. General legal information for self-represented litigants."
        ),
    },
    "traffic": {
        "title": _("Traffic & Fines"),
        "subtitle": _(
            "Traffic violations, fines, license issues, and your options"
        ),
        "description": _("Tickets, license issues, court fines"),
        "icon": "truck",
        "meta_description": _(
            "Learn about traffic tickets, fines, license suspension, and your options. General legal information for self-represented litigants."
        ),
    },
}


def health(request):
    """Lightweight health check for Fly.io."""
    return HttpResponse("ok")


def home(request):
    """Home page - dashboard with hero and topic grid."""
    return render(request, "pages/home.html", {"topics": TOPICS})


def topic_detail(request, slug):
    """Topic detail page - informational content about a legal topic."""
    topic = TOPICS.get(slug)
    if not topic:
        raise Http404(f"Topic '{slug}' not found")
    return render(request, f"pages/topics/{slug}.html", {"topic": topic})


def chat_page(request):
    """Chat page - AI-powered legal assistance chat interface."""
    return render(request, "pages/chat.html")


def test_agent(request, agent_name):
    """Test page for a specific agent."""
    if agent_name not in agent_registry:
        raise Http404(f"Agent '{agent_name}' not found")
    return render(request, "pages/chat.html", {"agent_name": agent_name})


def about(request):
    """About page - mission, disclaimers, FLP info."""
    return render(request, "pages/about.html")


def privacy(request):
    """Privacy page - data practices and user rights."""
    return render(request, "pages/privacy.html")


def accessibility(request):
    """Accessibility page - WCAG conformance and feedback."""
    return render(request, "pages/accessibility.html")


def style_guide(request):
    """Design tokens and component library"""
    return render(request, "pages/style_guide.html", {"topics": TOPICS})


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
    success_url = reverse_lazy("portal:profile")

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def form_valid(self, form):
        messages.success(
            self.request, gettext("Profile updated successfully.")
        )
        return super().form_valid(form)
