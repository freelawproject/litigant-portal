from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import DetailView, UpdateView

from chat.agents import agent_registry

from .forms import UserProfileForm
from .models import UserProfile


def health(request):
    """Lightweight health check for Fly.io."""
    return HttpResponse("ok")


def home(request):
    """Home page - main app landing page"""
    return render(request, "pages/home.html")


def test_agent(request, agent_name):
    """Test page for a specific agent."""
    if agent_name not in agent_registry:
        raise Http404(f"Agent '{agent_name}' not found")
    return render(request, "pages/home.html", {"agent_name": agent_name})


def dashboard_demo(request):
    """Recovered dashboard layout demo (pre-chat-first design)"""
    return render(request, "pages/dashboard_demo.html")


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
