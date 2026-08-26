import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import urlencode
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, UpdateView

from litigant_portal.app.forms import UserProfileForm
from litigant_portal.app.models import UserProfile
from litigant_portal.app.models.choices import (
    BedrockModel,
    JurisdictionLevel,
    OpenAIModel,
    State,
    get_default_model,
)
from litigant_portal.app.selectors.topic_flow import topic_list
from litigant_portal.app.services.topic_flow import variable_answer_set_many
from litigant_portal.app.topic_flow.registry import registry
from litigant_portal.app.topic_flow.renderer import (
    question_ids,
    render_section,
    submitted_section_anchor,
)
from litigant_portal.app.topic_flow.validation import validate_answers
from litigant_portal.app.views.utils import topic_flow_answers


def home(request):
    """Home page - dashboard with hero and topic grid."""
    topics = {t.slug: t for t in topic_list()}
    return render(request, "pages/home.html", {"topics": topics})


def chat_view(request):
    """Chat page"""
    return render(request, "pages/chat/index.html")


def deep_link(request, court, topic):
    """Deep-link entry: /t/{court}/{topic}/ → chat with both pre-set.

    Validates the pair against the prompt registries. Unknown court or
    topic returns 404. On success, 302 to /chat/?topic=X&court=Y so the
    existing chat page handles the heavy lifting.
    """
    from litigant_portal.prompts import is_known_court, is_known_topic

    if not is_known_topic(topic):
        raise Http404(f"Topic '{topic}' not registered")
    if not is_known_court(court):
        raise Http404(f"Court '{court}' not registered")

    query = urlencode({"topic": topic.lower(), "court": court.lower()})
    return redirect(f"{reverse('pages:chat')}?{query}")


def topic_flow(request, court, topic, role):
    """Topic Flow entry: /t/{court}/{topic}/{role}/ → rendered corpus sections.

    Resolves the corpus from the registry (404 on miss). GET renders each
    section via SectionRenderer with the visitor's stored answers (so
    fact_gather fields prefill). POST persists the submitted answers as
    VariableAnswer rows and redirects (PRG) so a reload re-GETs rather than
    re-submits — the whole flow works with JS off. The view stays thin:
    section dispatch lives in renderer.py, deadline math in deadlines.py.

    Saving marks answers ``reviewed=True``: this page is where a human
    confirms what the assistant guessed, and only reviewed answers may
    reach the docassemble prefill.
    """
    corpus = registry.get(court, topic, role)
    if corpus is None:
        raise Http404(f"No Topic Flow for {court}/{topic}/{role}")

    if request.method == "POST":
        submitted = {
            qid: request.POST[qid]
            for qid in question_ids(corpus)
            if qid in request.POST
        }
        errors = validate_answers(corpus, submitted)
        # Persist only what passes, canonicalized (stripped) to match what
        # validate_answers checked — otherwise a padded-but-valid answer
        # ("Cass  ") stores raw and fails the strict option-selected match on
        # re-render, and a padded date breaks date.fromisoformat in the
        # deadline compute. A blank required field or an out-of-list choice
        # never lands in the store; valid siblings still save. A blank
        # optional field stores None, which clears the answer.
        valid = {
            qid: submitted[qid].strip() or None
            for qid in submitted
            if qid not in errors
        }
        if valid:
            variable_answer_set_many(
                identity=request.identity, values=valid, reviewed=True
            )
        if errors:
            # Soft-gate: re-render in place (no PRG) with inline errors so the
            # litigant can fix and resubmit. Render from the stored answers
            # (not the raw submission), so a rejected value can't leak into the
            # summary while the form flags it. Other sections still render —
            # not a forward-only wizard.
            return _render_topic_flow(
                request, corpus, topic_flow_answers(request, corpus), errors
            )
        # PRG back to the section just saved (#anchor) so the litigant keeps
        # their place and sees the recomputed deadlines, instead of the browser
        # jumping to the top of the page on the redirected GET.
        url = reverse(
            "pages:topic_flow",
            kwargs={"court": court, "topic": topic, "role": role},
        )
        anchor = submitted_section_anchor(corpus, submitted)
        if anchor:
            url = f"{url}#{anchor}"
        return redirect(url)

    return _render_topic_flow(
        request, corpus, topic_flow_answers(request, corpus)
    )


def _render_topic_flow(request, corpus, answers, errors=None):
    """Render the full Topic Flow page from resolved answers.

    Shared by the GET path and the POST error re-render. ``errors`` (a
    ``{question_id: [message]}`` map) threads into ``render_section`` so a
    failed fact_gather submit shows inline errors; ``None`` on a clean render.
    """
    rendered_sections = [
        render_section(section, corpus, answers, errors)
        for section in corpus.sections
    ]
    # Table of contents for the in-header wayfinding menu — one entry per
    # headed section, so a litigant can jump back to re-read or revise.
    toc = [
        {"anchor": section.anchor_id, "heading": section.heading}
        for section in rendered_sections
        if section.heading
    ]
    return render(
        request,
        "pages/topic_flow.html",
        {
            "corpus": corpus,
            "rendered_sections": rendered_sections,
            "toc": toc,
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
@permission_required("app.manage_site", raise_exception=True)
def admin(request: HttpRequest) -> HttpResponse:
    """Admin dashboard shell."""
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
