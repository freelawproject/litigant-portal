import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse, reverse_lazy
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, UpdateView

from litigant_portal.app.forms import UserProfileForm
from litigant_portal.app.models import TopicFlow, UserProfile
from litigant_portal.app.models.choices import (
    BedrockModel,
    JurisdictionLevel,
    OpenAIModel,
    State,
    get_default_model,
)
from litigant_portal.app.selectors.site import (
    contact_list,
    resource_list,
)
from litigant_portal.app.selectors.topic_flow import (
    topic_flow_answer_values,
    topic_flow_get_public,
    topic_list,
)
from litigant_portal.app.services.topic_flow import (
    render_markdown,
    topic_flow_deadline_rows,
)


def home(request):
    """Home page - dashboard with hero and topic grid."""
    topics = {t.slug: t for t in topic_list()}
    return render(request, "pages/home.html", {"topics": topics})


def topic_detail(request, topic_slug):
    """Public topic page: cards for the topic's live flows."""
    topics = {t.slug: t for t in topic_list()}
    topic = topics.get(topic_slug)
    if topic is None:
        raise Http404(f"No Topic {topic_slug}")
    flows = [flow for flow in topic.flows.all() if flow.enabled]
    return render(
        request, "pages/topic.html", {"topic": topic, "flows": flows}
    )


def chat_view(request):
    """Chat page"""
    return render(request, "pages/chat/index.html")


# Temp demo URLs for hard-coded Docassemble flows
DOCASSEMBLE_DEMO_URLS = {
    ("adult-name-change", "standard"): (
        "https://qa.litigantportal.com/interview/interview"
        "?i=docassemble.playground1:petition-standard.yml"
    ),
    ("adult-name-change", "waiver"): (
        "https://qa.litigantportal.com/interview/interview"
        "?i=docassemble.playground1:petition-waiver.yml"
    ),
}


def topic_flow_detail(request, topic_slug, flow_slug):
    """Public Topic Flow page: sections, interview, deadlines, and downloads."""
    try:
        flow = topic_flow_get_public(
            topic_slug=topic_slug, flow_slug=flow_slug
        )
    except TopicFlow.DoesNotExist:
        raise Http404(f"No Topic Flow {topic_slug}/{flow_slug}")

    values = topic_flow_answer_values(identity=request.identity, flow=flow)
    slugs = {"topic_slug": topic_slug, "flow_slug": flow_slug}
    forms = [
        {
            "slug": form.slug,
            "name": form.name,
            "url": reverse(
                "topic_flow_api:form",
                kwargs={**slugs, "form_slug": form.slug},
            ),
        }
        for form in flow.forms.all()
    ]
    return render(
        request,
        "pages/flow.html",
        {
            "topic": flow.topic,
            "flow": flow,
            "sections": [
                {
                    "heading": section.heading,
                    "html": render_markdown(section.content),
                    "anchor": f"{slugify(section.heading) or 'section'}"
                    f"-{index}",
                }
                for index, section in enumerate(flow.sections.all(), start=1)
            ],
            "has_interview": bool(flow.fields),
            "interview_data_url": reverse(
                "topic_flow_api:interview", kwargs=slugs
            ),
            "deadlines": topic_flow_deadline_rows(flow=flow, values=values),
            "forms": forms,
            "links": flow.links.all(),
            "contacts": contact_list(),
            "resources": resource_list(),
            "has_forms": bool(forms),
            "interview_url": DOCASSEMBLE_DEMO_URLS.get(
                (topic_slug, flow_slug)
            ),
            "packet_url": reverse("topic_flow_api:packet", kwargs=slugs),
            "answers_url": reverse("topic_flow_api:answers", kwargs=slugs),
            "calendar_url": reverse("topic_flow_api:calendar", kwargs=slugs),
            "contacts_vcf_url": reverse(
                "topic_flow_api:contacts", kwargs=slugs
            ),
        },
    )


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
    topics = {t.slug: t for t in topic_list()}
    return render(request, "pages/style_guide.html", {"topics": topics})


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
    """Admin dashboard shell — requires the ``app.manage_site`` permission."""
    if not request.user.has_perm("app.manage_site"):
        raise PermissionDenied
    openai_available = bool(os.environ.get("OPENAI_API_KEY"))
    bedrock_available = bool(os.environ.get("AWS_BEARER_TOKEN_BEDROCK"))
    model_choice_groups = []
    if openai_available:
        model_choice_groups.append(("OpenAI", OpenAIModel.choices))
    if bedrock_available or not openai_available:
        model_choice_groups.append(("AWS Bedrock", BedrockModel.choices))
    all_model_labels = dict(OpenAIModel.choices) | dict(BedrockModel.choices)
    return render(
        request,
        "pages/admin/index.html",
        {
            "openai_available": openai_available,
            "bedrock_available": bedrock_available,
            "model_choice_groups": model_choice_groups,
            "default_model_label": all_model_labels[get_default_model()],
            "jurisdiction_choices": JurisdictionLevel.choices,
            "state_choices": State.choices,
        },
    )
