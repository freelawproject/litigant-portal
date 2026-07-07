from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse, reverse_lazy
from django.utils.http import urlencode
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _
from django.views.generic import DetailView, UpdateView

from litigant_portal.agents import agent_registry
from litigant_portal.app.forms import UserProfileForm
from litigant_portal.app.models import UserProfile
from litigant_portal.app.topic_flow.answer_store import AnswerStore
from litigant_portal.app.topic_flow.downloads import (
    build_download,
    find_downloadable,
)
from litigant_portal.app.topic_flow.registry import registry
from litigant_portal.app.topic_flow.renderer import (
    question_ids,
    render_section,
    submitted_section_anchor,
)
from litigant_portal.app.topic_flow.validation import validate_answers

TOPICS = {
    "eviction": {
        "title": _("Housing & Eviction"),
        "subtitle": _(
            "Understanding the eviction process, tenant rights, and landlord obligations"
        ),
        "description": _("Landlord disputes, eviction defense, tenant rights"),
        "icon": "home",
        "meta_description": _(
            "Learn about the eviction process, tenant rights, and landlord obligations. General legal information for self-represented litigants."
        ),
        "prompts": [
            _(
                "I received an eviction notice and need to understand my options"
            ),
            _("My landlord isn't making repairs — what are my rights?"),
            _("I'm behind on rent and worried about eviction"),
        ],
        "context_sections": [
            {
                "heading": _("The eviction process"),
                "body": _(
                    "Eviction follows a legal process: written notice, court"
                    " filing, hearing, judgment, and enforcement. A landlord"
                    " cannot skip steps or use self-help eviction (changing"
                    " locks, shutting off utilities)."
                ),
            },
            {
                "heading": _("Key tenant rights"),
                "body": _(
                    "You have the right to proper written notice, habitable"
                    " living conditions, protection from retaliation, freedom"
                    " from discrimination under the Fair Housing Act, and the"
                    " right to appear and respond in court."
                ),
            },
            {
                "heading": _("If you received a notice"),
                "body": _(
                    "Read the notice carefully and note any deadlines. Do not"
                    " ignore it — missing a court date usually results in a"
                    " default judgment. Gather your lease, rent receipts,"
                    " photos, and communications with your landlord."
                ),
            },
        ],
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
        "prompts": [],
        "context_sections": [],
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
        "prompts": [],
        "context_sections": [],
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
        "prompts": [],
        "context_sections": [],
    },
    "adult_name_change": {
        "title": _("Adult Name Change"),
        "subtitle": _(
            "Legally changing your name — standalone petition process"
        ),
        "description": _("Petition, publication, and records cascade"),
        "icon": "identification",
        "meta_description": _(
            "Learn about legally changing your name as an adult — petition process, publication requirements, and updating your records. General legal information for self-represented litigants."
        ),
        "prompts": [
            _("I want to change my last name back after a divorce"),
            _("I want to change my first or middle name"),
            _("What forms do I need for a name change?"),
        ],
        "context_sections": [
            {
                "heading": _("Standalone vs. divorce-bundled"),
                "body": _(
                    "An adult name change is usually a standalone court"
                    " petition, separate from any divorce case. If your divorce"
                    " decree didn't include a name change, you'll file a new"
                    " petition in your local district court."
                ),
            },
            {
                "heading": _("Two tracks: standard and waiver"),
                "body": _(
                    "Most jurisdictions offer two paths. A standard track —"
                    " for any change involving the last name — usually requires"
                    " publishing notice in a newspaper and a waiting period."
                    " A waiver track — for first or middle name only — may"
                    " allow the publication requirement to be waived by the"
                    " judge."
                ),
            },
            {
                "heading": _("What to know up front"),
                "body": _(
                    "You'll file a petition with supporting forms, pay a"
                    " filing fee (waivers are often available for"
                    " income-qualifying filers), and — on the standard track —"
                    " publish notice and wait before the judge reviews your"
                    " petition. Background check timing varies by judge; a"
                    " quick call to the clerk of court can confirm whether it"
                    " happens before or after you file."
                ),
            },
        ],
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
        "prompts": [],
        "context_sections": [],
    },
}


def home(request):
    """Home page - dashboard with hero and topic grid."""
    return render(request, "pages/home.html", {"topics": TOPICS})


def topic_detail(request, slug):
    """Topic detail page - informational content about a legal topic."""
    topic = TOPICS.get(slug)
    if not topic:
        raise Http404(f"Topic '{slug}' not found")
    return render(
        request, f"pages/topics/{slug}.html", {"topic": topic, "slug": slug}
    )


def chat_page(request):
    """Chat page - AI-powered legal assistance chat interface."""
    from litigant_portal.app.court_context import (
        get_active_court,
        set_active_court,
    )
    from litigant_portal.prompts import get_court_name, is_known_court

    slug = request.GET.get("topic", "").strip()
    topic = TOPICS.get(slug) if slug else None
    topic_context = ""
    if topic and topic.get("context_sections"):
        lines = [f"Topic: {topic['title']}"]
        for section in topic["context_sections"]:
            lines.append(f"{section['heading']}: {section['body']}")
        topic_context = "\n".join(lines)

    # Active court comes from the session (demo switcher, #632). An explicit,
    # valid ?court= (deep-link path) overrides and persists it, so the chosen
    # court sticks across navigation instead of living only in the URL.
    court_slug = get_active_court(request)
    param_court = request.GET.get("court", "").strip().lower()
    if (
        param_court
        and is_known_court(param_court)
        and param_court != court_slug
    ):
        court_slug = set_active_court(request, param_court)

    return render(
        request,
        "pages/chat.html",
        {
            "topic": topic,
            "topic_slug": slug if topic else "",
            "topic_context": topic_context,
            "court_slug": court_slug,
            "court_name": get_court_name(court_slug),
        },
    )


def set_court(request):
    """Demo court switcher: set the session's active court, then redirect back.

    Dev/QA only (#632) — hidden and inert in production, where the court comes
    from a per-court config object rather than a user switcher. POST only; a
    blank / unknown court clears the selection (the generic, no-court option).
    """
    from django.utils.http import url_has_allowed_host_and_scheme

    from litigant_portal.app.court_context import (
        set_active_court,
        switcher_enabled,
    )

    if not switcher_enabled() or request.method != "POST":
        raise Http404()

    set_active_court(request, request.POST.get("court", ""))

    nxt = request.POST.get("next", "")
    if url_has_allowed_host_and_scheme(
        nxt, allowed_hosts={request.get_host()}
    ):
        return redirect(nxt)
    return redirect("pages:home")


def chat_v2_view(request):
    """New chat page"""
    return render(request, "chat_v2/index.html")


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
    section via SectionRenderer with the guest's stored answers (so fact_gather
    fields prefill). POST persists the submitted answers to the session-backed
    AnswerStore and redirects (PRG) so a reload re-GETs rather than re-submits —
    the whole flow works with JS off. The view stays thin: section dispatch
    lives in renderer.py, deadline math in deadlines.py.
    """
    corpus = registry.get(court, topic, role)
    if corpus is None:
        raise Http404(f"No Topic Flow for {court}/{topic}/{role}")

    store = AnswerStore(request.session, court, topic, role)

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
        # never lands in the store; valid siblings still save.
        valid = {
            qid: submitted[qid].strip()
            for qid in submitted
            if qid not in errors
        }
        if valid:
            store.update(valid)
        if errors:
            # Soft-gate: re-render in place (no PRG) with inline errors so the
            # litigant can fix and resubmit. Render from the stored answers
            # (not the raw submission), so a rejected value can't leak into the
            # summary while the form flags it. Other sections still render —
            # not a forward-only wizard.
            return _render_topic_flow(request, corpus, store.all(), errors)
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

    return _render_topic_flow(request, corpus, store.all())


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


def topic_flow_download(request, court, topic, role, output_id):
    """Download a Topic Flow output section as a file (e.g. an ``.ics``).

    The generic counterpart to ``topic_flow``: resolve the corpus and the
    downloadable output section (404 on either miss — an unknown id or a
    non-downloadable section), then dispatch on ``output_type`` to assemble the
    file from the guest's stored answers. The view stays thin — file bytes come
    from the download handlers in downloads.py, computed from the same
    AnswerStore the page renders, so the download matches what's on screen.
    """
    corpus = registry.get(court, topic, role)
    if corpus is None:
        raise Http404(f"No Topic Flow for {court}/{topic}/{role}")

    section = find_downloadable(corpus, output_id)
    if section is None:
        raise Http404(f"No downloadable output {output_id!r}")

    store = AnswerStore(request.session, court, topic, role)
    artifact = build_download(section, corpus, store.all())
    response = HttpResponse(artifact.body, content_type=artifact.content_type)
    response["Content-Disposition"] = (
        f'attachment; filename="{artifact.filename}"'
    )
    return response


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
    success_url = reverse_lazy("pages:profile")

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        return profile

    def form_valid(self, form):
        messages.success(
            self.request, gettext("Profile updated successfully.")
        )
        return super().form_valid(form)
