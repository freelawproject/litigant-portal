import os
from urllib.parse import urlsplit

from django.conf import settings
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
from litigant_portal.app.selectors.site import (
    contact_help_list,
    contact_list,
    resource_list,
    site_get,
)
from litigant_portal.app.selectors.topic_flow import topic_list
from litigant_portal.app.services.topic_flow import variable_answer_set_many
from litigant_portal.app.services.user import user_identity_reset
from litigant_portal.app.topic_flow import rows
from litigant_portal.app.topic_flow.registry import registry
from litigant_portal.app.topic_flow.renderer import (
    NEVER_PREFILL,
    question_ids,
    render_section,
    submitted_section_anchor,
)
from litigant_portal.app.topic_flow.validation import validate_answers
from litigant_portal.app.views.utils import (
    admin_tabs,
    briefcase_answers,
    topic_flow_answers,
    topic_flow_row_answers,
    topic_flow_row_cleared_names,
    topic_flow_row_get,
)


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
    if settings.TOPIC_FLOW_SOURCE == "corpus":
        return topic_flow_rows(request, court, topic, role)

    corpus = registry.get(court, topic, role)
    if corpus is None:
        raise Http404(f"No Topic Flow for {court}/{topic}/{role}")

    if request.method == "POST":
        submitted, errors, valid = _accepted_answers(
            request.POST,
            question_ids(corpus),
            lambda s: validate_answers(corpus, s),
            lambda _name, raw: raw.strip() or None,
            NEVER_PREFILL,
        )
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
        if valid:
            # A NEVER_PREFILL field re-renders blank even after a successful
            # save, so without a toast the save looks like it failed (#803).
            _flash_saved(request, valid, NEVER_PREFILL)
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


def _accepted_answers(post, names, validate, coerce, protected):
    """``(submitted, errors, valid)`` for a fact form POST.

    ``submitted`` is the posted strings for ``names``; ``errors`` is
    ``{name: [message]}``; ``valid`` is the typed values to store.
    ``protected`` names the fields that render blank even when stored
    (``NEVER_PREFILL`` on the content path, the glossary's private flag on
    the rows path): a blank one is skipped unless its clear checkbox was
    posted (a blank there means "not shown", not "erase").
    """
    submitted = {name: post[name] for name in names if name in post}
    errors = validate(submitted)
    valid = {}
    for name, raw in submitted.items():
        if name in errors:
            continue
        value = coerce(name, raw)
        if (
            value is None
            and name in protected
            and f"{name}__clear" not in post
        ):
            continue
        valid[name] = value
    return submitted, errors, valid


def _flash_saved(request, valid, protected, revealed=()):
    """The toast after a save. A ``protected`` field re-renders blank even
    after a successful save, so without the longer message the save looks
    like it failed (#803). ``revealed`` names the questions the save
    uncovered, so a screen reader hears that the page is not done (WCAG
    4.1.3); a gate can reveal a question on an earlier page, so the toast
    does not say where. Shared by both page sources."""
    private = any(valid.get(name) for name in protected)
    if revealed and private:
        text = _(
            "Saved. More questions appeared on this page. For your privacy, "
            "your answers are not shown here."
        )
    elif revealed:
        text = _("Saved. More questions appeared on this page.")
    elif private:
        text = _(
            "Saved. For your privacy, your answers are not shown on this page."
        )
    else:
        text = _("Saved.")
    messages.success(request, text)


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
    return _render_flow_page(
        request, corpus.metadata.title, rendered_sections, corpus=corpus
    )


def topic_flow_rows(request, court, topic, role):
    """The guided page built from TopicFlow rows (``TOPIC_FLOW_SOURCE=corpus``,
    #1016).

    The sibling of ``topic_flow`` that reads the rows ``sync_corpus`` writes.
    """
    flow = topic_flow_row_get(court, topic, role)
    sections = list(flow.sections.all())
    pages = rows.flow_pages(flow)
    form_conditions = list(flow.form_conditions.all())
    deadlines = list(flow.deadlines.all())
    names = rows.flow_variable_names(pages, form_conditions, deadlines)
    answers = topic_flow_row_answers(request, names)
    cleared = topic_flow_row_cleared_names(request, names)
    # The output blocks' rows (the URL's court's whole contact and resource
    # lists, not a per-flow pick) and the URL parts their links need.
    block_rows = {
        "form_conditions": form_conditions,
        "deadlines": deadlines,
        "contacts": contact_list(court=court),
        "resources": resource_list(court=court),
        "court": court,
        "topic": topic,
        "role": role,
    }

    if request.method == "POST":
        # Same rules as the content path's POST above, over glossary rows.
        # Only currently asked variables are read, so a gated field whose
        # gate is unmet is ignored even if posted. A stored private field
        # renders blank, so a blank there is "keep", not "missing".
        variables = {v.name: v for _page, placed in pages for v in placed}
        asked = rows.asked_names(pages, answers)
        private = rows.private_names(pages)
        keep = {n for n in asked if n in private and n in answers}
        submitted, errors, valid = _accepted_answers(
            request.POST,
            asked,
            lambda s: rows.validate_answers(variables.values(), s, keep),
            lambda name, raw: rows.coerce_value(variables[name], raw),
            private,
        )
        # An untouched field re-saves its stored value, not the form's
        # narrower string of it (a datetime's zone, a float's type).
        valid = rows.restore_unchanged(variables, submitted, answers, valid)
        # A gated answer whose gate stops matching is cleared with the save,
        # so the briefcase and the prefill agree with the page.
        for name in rows.stale_gated_names(pages, answers, valid):
            valid[name] = None
        revealed = []
        if valid:
            variable_answer_set_many(
                identity=request.identity, values=valid, reviewed=True
            )
            # Re-read: a gate just saved decides which fields show next,
            # and the ones it uncovered get the toast and the anchor.
            answers = topic_flow_row_answers(request, names)
            cleared = topic_flow_row_cleared_names(request, names)
            asked_after = rows.asked_names(pages, answers)
            revealed = [name for name in asked_after if name not in asked]
            # A gate flipped by this save hides its dependents, so an error
            # on one has no field to land on: drop it rather than re-render
            # a page that shows no message.
            errors = {
                name: found
                for name, found in errors.items()
                if name in asked_after
            }
        if errors:
            return _render_flow_page(
                request,
                flow.name,
                rows.render_flow(
                    flow,
                    sections,
                    pages,
                    answers,
                    errors,
                    cleared,
                    **block_rows,
                ),
            )
        if valid:
            _flash_saved(request, valid, private, revealed)
        url = reverse(
            "pages:topic_flow",
            kwargs={"court": court, "topic": topic, "role": role},
        )
        # Field ids are variable names, so landing on the first revealed
        # question puts focus in it; otherwise back to the section saved.
        anchor = (
            revealed[0]
            if revealed
            else rows.submitted_section_anchor(pages, submitted)
        )
        if anchor:
            url = f"{url}#{anchor}"
        return redirect(url)

    return _render_flow_page(
        request,
        flow.name,
        rows.render_flow(
            flow, sections, pages, answers, cleared=cleared, **block_rows
        ),
    )


def _render_flow_page(request, page_title, rendered_sections, **extra):
    """Render ``pages/topic_flow.html`` from an ordered ``RenderedSection``
    list, whichever source built it."""
    section_links = [
        {"anchor": section.anchor_id, "heading": section.heading}
        for section in rendered_sections
        if section.heading
    ]
    return render(
        request,
        "pages/topic_flow.html",
        {
            "page_title": page_title,
            "rendered_sections": rendered_sections,
            "section_links": section_links,
            "frame_left_label": _("Sections"),
            "frame_left_icon": "list-bullet",
            "briefcase_groups": briefcase_answers(request),
            **extra,
        },
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
