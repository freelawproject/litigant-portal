from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import DetailView, UpdateView

from chat.agents import agent_registry

from .forms import UserProfileForm
from .models import UserProfile

TOPICS = {
    "housing": {
        "title": "Housing & Eviction",
        "subtitle": "Understanding the eviction process, tenant rights, and landlord obligations",
        "icon": "home",
        "meta_description": "Learn about the eviction process, tenant rights, and landlord obligations. General legal information for self-represented litigants.",
    },
    "family": {
        "title": "Family & Divorce",
        "subtitle": "Divorce, custody, child support, and domestic violence resources",
        "icon": "users",
        "meta_description": "Learn about divorce, child custody, child support, and family court. General legal information for self-represented litigants.",
    },
    "small-claims": {
        "title": "Small Claims",
        "subtitle": "Resolving disputes and understanding the small claims court process",
        "icon": "currency-dollar",
        "meta_description": "Learn about filing or defending a small claims case. General legal information for self-represented litigants.",
    },
    "consumer": {
        "title": "Consumer Rights",
        "subtitle": "Debt collection rules, contract disputes, and consumer protections",
        "icon": "shield-check",
        "meta_description": "Learn about consumer rights, debt collection rules, and contract disputes. General legal information for self-represented litigants.",
    },
    "expungement": {
        "title": "Expungement",
        "subtitle": "Clearing or sealing your criminal record and restoring opportunities",
        "icon": "document-text",
        "meta_description": "Learn about expungement, record sealing, and eligibility requirements. General legal information for self-represented litigants.",
    },
    "traffic": {
        "title": "Traffic & Fines",
        "subtitle": "Traffic violations, fines, license issues, and your options",
        "icon": "truck",
        "meta_description": "Learn about traffic tickets, fines, license suspension, and your options. General legal information for self-represented litigants.",
    },
}


def health(request):
    """Lightweight health check for Fly.io."""
    return HttpResponse("ok")


def home(request):
    """Home page - dashboard with hero and topic grid."""
    return render(request, "pages/home.html")


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
    return render(request, "pages/style_guide.html")


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
        messages.success(self.request, "Profile updated successfully.")
        return super().form_valid(form)
