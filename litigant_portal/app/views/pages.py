import os
import re

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseNotAllowed,
)
from django.shortcuts import redirect, render
from django.template.loader import get_template
from django.templatetags.static import static
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.utils.translation import gettext_lazy as _
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.generic import DetailView, UpdateView

from litigant_portal.app.forms import UserProfileForm
from litigant_portal.app.models import (
    UserProfile,
    Variable,
    VariableAnswer,
)
from litigant_portal.app.models.choices import (
    DEFAULT_BEDROCK_MODEL,
    DEFAULT_FAST_BEDROCK_MODEL,
    BedrockModel,
    JurisdictionLevel,
    State,
    VariableDataType,
)
from litigant_portal.app.selectors.topic_flow import topic_list
from litigant_portal.app.services.topic_flow import variable_answer_set_many
from litigant_portal.app.services.user import user_identity_reset
from litigant_portal.app.theme import (
    contrast_level,
    contrast_ratio,
    theme_colors,
)
from litigant_portal.app.topic_flow.registry import registry
from litigant_portal.app.topic_flow.renderer import (
    NEVER_PREFILL,
    question_ids,
    render_section,
    submitted_section_anchor,
)
from litigant_portal.app.topic_flow.validation import validate_answers
from litigant_portal.app.views.utils import (
    briefcase_answers,
    topic_flow_answers,
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
        # optional field stores None, which clears the answer — except for a
        # NEVER_PREFILL field, which renders blank whatever is stored, so a
        # blank submission there means "never shown", not "erase it". Erasing
        # one takes its explicit clear checkbox; a typed value wins over the
        # checkbox, since replacing is the stronger intent.
        valid = {}
        for qid, raw in submitted.items():
            if qid in errors:
                continue
            value = raw.strip() or None
            if (
                value is None
                and qid in NEVER_PREFILL
                and f"{qid}__clear" not in request.POST
            ):
                continue
            valid[qid] = value
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
            if any(valid.get(qid) for qid in NEVER_PREFILL):
                messages.success(
                    request,
                    _(
                        "Saved. For your privacy, your answers are not "
                        "shown on this page."
                    ),
                )
            else:
                messages.success(request, _("Saved."))
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
    # The flow's sections for the frame's left region: one entry per headed
    # section, so a litigant can jump back to re-read or revise.
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
            "frame_left_label": _("Sections"),
            "frame_left_icon": "list-bullet",
            "briefcase_groups": briefcase_answers(request),
        },
    )


def start_over(request):
    """Dev and QA only: start the session over from the seeded defaults
    (#969).

    Deletes the visitor's chats, uploads and answers, then returns to
    ``next`` when it is on this site. The site menu asks for confirmation
    first. Production answers 404 here, whatever the menu shows, so the
    check lives on the server and not only in the template.
    """
    # Before the method check, so every method 404s in production and none
    # gives away that the endpoint exists.
    if settings.DEPLOYMENT_ENV == "prod":
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
    return redirect(next_url)


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
    return render(
        request,
        "pages/style_guide.html",
        {
            "topics": topics,
            "briefcase_groups": _briefcase_sample(),
            "internal_section": "style_guide",
        },
    )


# Stages the Atomic Design summary page frames, smallest first. The fifth
# column, "page", is the real home page rather than a stage of its own.
ATOMIC_DESIGN_STAGES = ("atoms", "molecules", "organisms", "template")

# Stand-in content for the stages below "page", so the columns show
# structure with no real court or topic in it.
ATOMIC_PLACEHOLDER_TOPICS = {
    f"topic-{number}": {
        "icon": "question-mark-circle",
        "title": "Topic name",
        "description": "One line about what this topic covers",
    }
    for number in range(1, 4)
}


# The five levels of the Atomic Design page, smallest first. "summary" is
# for stakeholders, "code" for developers: where the pieces live. The atom,
# molecule and organism levels have no "code" here; theirs is read from the
# sample template (see _sample_components), so it can't drift from it. "sample"
# is the width the rendered sample is shown at, each the smallest real place
# that level lives: atoms inline (no layout of their own), molecules in a
# phone, organisms in the content column, template and page in the window
# (a fixed-height frame filling the content column beside the sidebar;
# "Open full size" shows them at true window width). "phone_view" offers a
# 375px view of the wider samples.
_ATOMIC_DESIGN_LEVELS = (
    {
        "stage": "atoms",
        "name": _("Atoms"),
        "summary": _(
            "The smallest pieces: an icon, a button, a search box. Each "
            "one carries its own accessibility rules, so everything built "
            "from it inherits them."
        ),
        "detail": "",
        "sample": "inline",
        "phone_view": False,
    },
    {
        "stage": "molecules",
        "name": _("Molecules"),
        "summary": _(
            "A few atoms joined to do one job. The logo links home; the "
            "search bar finds help; a topic card opens a topic."
        ),
        "detail": _(
            "Molecules get reused in small spaces, so they are shown at "
            "phone width."
        ),
        "sample": "phone",
        "phone_view": False,
    },
    {
        "stage": "organisms",
        "name": _("Organisms"),
        "summary": _(
            "Whole sections of a page, built from molecules: the header, "
            "the topic list, the sign-in box."
        ),
        "detail": _(
            "The test for an organism: could it be dropped onto a different "
            "page and still make sense on its own? The header can. The logo "
            "inside it is a molecule: it does one small job, and on its own "
            "it is not a section of anything."
        ),
        "sample": "content",
        "phone_view": True,
    },
    {
        "stage": "template",
        "name": _("Template"),
        "summary": _(
            "The sections placed into the page frame, filled with stand-in "
            "content. This is the layout, without a real court or topic in "
            "it."
        ),
        "detail": _(
            "Where the organisms go and in what order. In our code that is a "
            "Django template file, and every framed page extends "
            "frame_base.html, which builds on base.html."
        ),
        "code": "frame_base.html + pages/home.html, with placeholder data",
        "sample": "window",
        "phone_view": True,
    },
    {
        "stage": "page",
        "name": _("Page"),
        "summary": _(
            "The same template with real content: the home page a litigant "
            "sees right now."
        ),
        "detail": "",
        "code": "pages/home.html, rendered by views/pages.py home()",
        "sample": "window",
        "phone_view": True,
    },
)


_SAMPLE_TAG = re.compile(
    r"<c-(?:atoms|molecules|organisms)\.([\w-]+)"
    r"|{%\s*include\s+\"([^\"]+)\""
)


def _sample_components(template_name: str) -> list[str]:
    """The components a sample template renders, each once, in first-use
    order. Includes are followed, so a sample split across files reads as
    one."""
    # The raw file, not .template.source: Cotton's loader has already
    # compiled the <c-...> tags in that.
    with open(get_template(template_name).origin.name) as f:
        source = f.read()
    names: list[str] = []
    for component, include in _SAMPLE_TAG.findall(source):
        names += [component] if component else _sample_components(include)
    return list(dict.fromkeys(names))


def atomic_design(request):
    """Atomic Design: the five levels in a sidebar, one level's live sample
    beside them.

    The level and viewport come from the query string, so the selector is
    plain links and works without JS. An unknown level falls back to atoms;
    a phone view is only offered for the levels wider than a phone. Every
    sample renders the real components, so a change shows on next reload.
    """
    stages = [level["stage"] for level in _ATOMIC_DESIGN_LEVELS]
    selected = request.GET.get("level")
    if selected not in stages:
        selected = stages[0]
    levels = [
        {
            **level,
            "href": f"?level={level['stage']}",
            "is_current": level["stage"] == selected,
        }
        for level in _ATOMIC_DESIGN_LEVELS
    ]
    current = next(level for level in levels if level["is_current"])
    if "code" not in current:
        components = _sample_components(
            f"pages/atomic_design/{current['stage']}.html"
        )
        current["code"] = (
            f"cotton/{current['stage']}/: {', '.join(components)}"
        )
    current["frame_url"] = (
        reverse("pages:home")
        if current["stage"] == "page"
        else reverse("pages:atomic_design_stage", args=[current["stage"]])
    )
    current["phone"] = (
        current["phone_view"] and request.GET.get("viewport") == "phone"
    )
    return render(
        request,
        "pages/atomic_design/index.html",
        {
            "levels": levels,
            "current": current,
            "internal_section": "atomic_design",
        },
    )


# Simulations the Accessibility page can apply to its demos, grouped as the
# switcher shows them: typical vision on its own, then colour vision, then
# low vision. Each key is also a CSS class suffix (a11y-sim-<key>) in
# main.css, and names the switcher radio (#sim-<key>) that main.css watches
# with :has(). Typical vision, the empty key, applies no simulation.
_A11Y_SIMULATION_GROUPS = (
    ("", "", (("", _("Typical vision")),)),
    (
        "colour",
        _("Colour vision"),
        (
            ("protanopia", _("Red-blind")),
            ("deuteranopia", _("Green-blind")),
            ("tritanopia", _("Blue-blind")),
            ("achromatopsia", _("No colour")),
        ),
    ),
    (
        "low",
        _("Low vision"),
        (
            ("blur", _("Blurred")),
            ("cataracts", _("Cataracts")),
            ("glaucoma", _("Glaucoma")),
        ),
    ),
)

# The simulation each section's "Try it" link switches on: (section id,
# simulation key). The template reads each link as try_it.<section id>, with
# hyphens as underscores, since a template variable can't hold a hyphen.
_A11Y_TRY_IT = (
    ("contrast", "cataracts"),
    ("colour-alone", "deuteranopia"),
)

# Text colours on white, chosen to show pass, borderline and fail. The fail
# sample is our own placeholder colour. Class names are written out in full
# so Tailwind's scanner finds them.
_A11Y_CONTRAST_SAMPLES = (
    ("greyscale-700", "white", "text-greyscale-700"),
    ("greyscale-500", "white", "text-greyscale-500"),
    ("greyscale-400", "white", "text-greyscale-400"),
)

# Levels that pass for body text. "AA large text" (3:1) does not: the
# contrast samples are body-size text.
_A11Y_BODY_TEXT_PASSING_LEVELS = ("AAA", "AA")

# The two copies of each demo for the "Compare with typical vision" toggle.
# The copy is aria-hidden and inert, and main.css shows it only while the
# toggle is checked; the simulation filter skips it.
_A11Y_DEMO_COPIES = (
    {"is_copy": False, "suffix": "", "caption": _("Simulated")},
    {"is_copy": True, "suffix": "-typical", "caption": _("Typical vision")},
)


def a11y_guide(request):
    """Accessibility (A11y): what WCAG protects against, shown on our own
    components, seen through a vision simulation.

    The switcher is radios that main.css watches with :has(), so switching
    needs no reload and no JS. ?simulate=<key> pre-checks one, so a link can
    open the page with a simulation on; an unknown key falls back to typical
    vision, so exactly one radio is always checked.
    """
    labels = {
        key: label
        for _group, _group_label, options in _A11Y_SIMULATION_GROUPS
        for key, label in options
    }
    selected = request.GET.get("simulate", "")
    if selected not in labels:
        selected = ""
    simulation_groups = [
        {
            "key": group,
            "label": group_label,
            "options": [
                {
                    "key": key,
                    "label": label,
                    "input_id": f"sim-{key or 'typical'}",
                    "checked": key == selected,
                }
                for key, label in options
            ],
        }
        for group, group_label, options in _A11Y_SIMULATION_GROUPS
    ]
    try_it = {
        section.replace("-", "_"): {
            "href": f"?simulate={key}#{section}",
            "label": labels[key],
        }
        for section, key in _A11Y_TRY_IT
    }
    colors = theme_colors()
    contrast_samples = []
    for foreground, background, text_class in _A11Y_CONTRAST_SAMPLES:
        ratio = contrast_ratio(colors[foreground], colors[background])
        level = contrast_level(ratio)
        passes = level in _A11Y_BODY_TEXT_PASSING_LEVELS
        contrast_samples.append(
            {
                "foreground": foreground,
                "background": background,
                "text_class": text_class,
                "ratio": ratio,
                "level": level,
                "passes": passes,
                "label": f"{ratio}:1, {level}" if passes else f"{ratio}:1",
            }
        )
    return render(
        request,
        "pages/a11y_guide.html",
        {
            "simulation_groups": simulation_groups,
            "try_it": try_it,
            # The demos render twice when compared: the simulated copy,
            # then an inert typical-vision copy. "suffix" keeps ids unique.
            "demo_copies": _A11Y_DEMO_COPIES,
            "contrast_samples": contrast_samples,
            # Shown on the passing form-field example, so its error state
            # renders without a submitted form.
            "name_errors": [
                _("Enter your full legal name, as it appears on your ID.")
            ],
            "internal_section": "a11y",
        },
    )


@xframe_options_sameorigin
def atomic_design_stage(request, stage):
    """One column of the Atomic Design summary, rendered to be framed.

    The template stage renders the home page's own template with
    placeholder data, so template and page differ only in their data.
    """
    if stage not in ATOMIC_DESIGN_STAGES:
        raise Http404
    context = {
        "topics": ATOMIC_PLACEHOLDER_TOPICS,
        "court_logo": static("images/style_guide/placeholder_court_logo.svg"),
        "court_name": "Court name",
    }
    if stage == "template":
        return render(request, "pages/home.html", context)
    return render(request, f"pages/atomic_design/{stage}.html", context)


def _briefcase_sample() -> list[dict]:
    """Unsaved sample facts for the style guide's briefcase entry.

    Built in memory rather than queried so the page renders the same on a
    fresh database, and so browsing the style guide never shows a real
    visitor's answers.
    """

    def fact(name, label, value, data_type=VariableDataType.TEXT):
        return VariableAnswer(
            variable=Variable(name=name, label=label, data_type=data_type),
            value=value,
        )

    return [
        {
            "title": "About you",
            "answers": [
                fact("tenant_first", "First name", "Jamie"),
                fact("tenant_last", "Last name", "Rivera"),
            ],
        },
        {
            "title": "Your notice",
            "answers": [
                fact(
                    "received_date",
                    "Date received",
                    "2026-09-01",
                    VariableDataType.DATE,
                ),
                fact("notice_reason", "Reason given", ["Unpaid rent"]),
            ],
        },
        {
            "title": "",
            "answers": [
                fact("court_name", "Court", "Franklin County Municipal Court")
            ],
        },
    ]


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
