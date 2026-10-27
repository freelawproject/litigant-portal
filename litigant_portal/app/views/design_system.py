import re
from functools import wraps

from django.http import Http404
from django.shortcuts import render
from django.template.loader import get_template
from django.templatetags.static import static
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.clickjacking import xframe_options_sameorigin

from litigant_portal.app.features import features
from litigant_portal.app.models import Variable, VariableAnswer
from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.theme import (
    contrast_level,
    contrast_ratio,
    theme_colors,
)
from litigant_portal.app.views.utils import topic_flow_cards


def _style_guide_required(view):
    """The design-system pages are a tester tool (#1037): on wherever
    ``features().style_guide`` is, a 404 everywhere else, so the gate
    holds by URL and not only in the menu."""

    @wraps(view)
    def gated(request, *args, **kwargs):
        if not features().style_guide:
            raise Http404
        return view(request, *args, **kwargs)

    return gated


@_style_guide_required
def style_guide(request):
    """Design tokens and component library"""
    return render(
        request,
        "pages/style_guide.html",
        {
            "topic_cards": topic_flow_cards(),
            "briefcase_groups": _briefcase_sample(),
            "internal_section": "style_guide",
        },
    )


# Stages the Atomic Design summary page frames, smallest first. The fifth
# column, "page", is the real home page rather than a stage of its own.
ATOMIC_DESIGN_STAGES = ("atoms", "molecules", "organisms", "template")

# Stand-in content for the stages below "page", so the columns show
# structure with no real court or topic in it.
ATOMIC_PLACEHOLDER_TOPIC_CARDS = [
    {
        "icon": "question-mark-circle",
        "title": "Topic name",
        "description": "One line about what this topic covers",
        "url": "#",
    }
] * 3


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


@_style_guide_required
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
# sample is the placeholder colour our inputs used before #984. Class names
# are written out in full so Tailwind's scanner finds them.
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


@_style_guide_required
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
@_style_guide_required
def atomic_design_stage(request, stage):
    """One column of the Atomic Design summary, rendered to be framed.

    The template stage renders the home page's own template with
    placeholder data, so template and page differ only in their data.
    """
    if stage not in ATOMIC_DESIGN_STAGES:
        raise Http404
    context = {
        "topic_cards": ATOMIC_PLACEHOLDER_TOPIC_CARDS,
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
