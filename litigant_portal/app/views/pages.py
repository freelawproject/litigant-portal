from urllib.parse import urlsplit

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
)
from django.shortcuts import redirect, render, resolve_url
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext_lazy as _
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_http_methods
from django.views.generic import DetailView, UpdateView

from litigant_portal.agents.bedrock import (
    BedrockModelUnavailable,
    default_model,
)
from litigant_portal.app.features import features
from litigant_portal.app.forms import UserProfileForm
from litigant_portal.app.models import UserProfile
from litigant_portal.app.models.choices import (
    JurisdictionLevel,
    State,
)
from litigant_portal.app.selectors.bedrock import (
    bedrock_catalog_get,
    bedrock_model_choices,
)
from litigant_portal.app.selectors.corpus import COURTS_DIR, corpus_load_courts
from litigant_portal.app.selectors.site import contact_help_list, site_get
from litigant_portal.app.services.corpus import corpus_court_switch
from litigant_portal.app.services.user import (
    user_identity_anonymous_settle,
    user_identity_delete_anonymous,
    user_identity_merge_anonymous,
    user_identity_reset,
)
from litigant_portal.app.session import ANONYMOUS_SESSION_KEY
from litigant_portal.app.views.utils import (
    ALL_COURTS,
    BRANDING_FIELDS,
    activity_threads,
    admin_tabs,
    briefcase_answers,
    role_choices,
    topic_flow_cards,
)


# The Atomic Design summary page frames the real home page as its "page"
# column, so home opts in to same-origin framing (Django's default is DENY).
@xframe_options_sameorigin
def home(request):
    """Home page - dashboard with hero and topic grid."""
    return render(
        request,
        "pages/home.html",
        {
            "topic_cards": topic_flow_cards(),
            "briefcase_groups": briefcase_answers(request),
            "activity_threads": activity_threads(request),
        },
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
    next_url = _next_url(request, default=reverse("pages:home"))
    return redirect(urlsplit(next_url).path)


def _next_url(request, *, default: str) -> str:
    """The ``next`` of the request when it is on this site, else
    ``default``."""
    next_url = request.POST.get("next", request.GET.get("next", ""))
    if url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return default


@login_required
@require_http_methods(["GET", "POST"])
def anonymous_answers(request):
    """Ask a signed-in visitor whether to keep what they did on this
    device before signing in: the answers, chats and uploads of the
    anonymous session whose key the middleware left in the session.

    GET shows the counts with a keep and a discard button; POST acts on
    the choice, forgets the key, and returns to ``next`` when it is on
    this site, else to ``LOGIN_REDIRECT_URL``. With nothing to bring, GET
    returns there at once.
    """
    next_url = _next_url(
        request, default=resolve_url(settings.LOGIN_REDIRECT_URL)
    )
    session_key = request.session.get(ANONYMOUS_SESSION_KEY, "")
    counts = user_identity_anonymous_settle(session_key=session_key)
    if not any(counts.values()):
        request.session.pop(ANONYMOUS_SESSION_KEY, None)
        return redirect(next_url)
    if request.method != "POST":
        return render(
            request,
            "account/answers.html",
            {"counts": counts, "next": next_url},
        )
    choice = request.POST.get("choice")
    if choice == "keep":
        user_identity_merge_anonymous(
            user=request.user, session_key=session_key
        )
    elif choice == "discard":
        user_identity_delete_anonymous(
            user=request.user, session_key=session_key
        )
    else:
        return HttpResponseBadRequest()
    request.session.pop(ANONYMOUS_SESSION_KEY, None)
    return redirect(next_url)


def court_switch(request):
    """Tester tool: resync this site to one court, or to every court
    (#886). On wherever ``features().court_switcher`` is (dev and QA).

    The switch is site-wide, so it changes the court for everyone on the
    site until the next switch, deploy or restart, and only FLP Staff
    (``app.manage_site``) may make it. It never touches sessions or
    answers. Returns home, since the old court's flow pages no longer
    exist.
    """
    # Before the permission and method checks, as in start_over: where
    # it's off, every request 404s, so nothing gives away that the
    # endpoint exists. That order is why this isn't @permission_required.
    if not features().court_switcher:
        raise Http404
    if not request.user.has_perm("app.manage_site"):
        raise PermissionDenied
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    slug = request.POST.get("court", "")
    courts = corpus_load_courts(with_topics=True)
    if slug != ALL_COURTS and slug not in courts:
        return HttpResponseBadRequest()
    if slug == ALL_COURTS:
        summary = corpus_court_switch(court=None)
        court_label = _("all courts")
    else:
        summary = corpus_court_switch(court=slug)
        court_label = courts[slug].name
    messages.success(
        request,
        _("Switched to %(court)s: %(topics)d topics, %(flows)d flows.")
        % {"court": court_label, **summary},
    )
    return redirect("pages:home")


def court_branding(request, court, field):
    """Tester tool: one court's logo or name image, straight from the corpus
    (#886). The court switcher's list shows every court's seal and name, but
    only the current court's branding is copied into storage by a sync.
    404 wherever ``features().court_switcher`` is off, and for a court,
    field or file the corpus doesn't have."""
    if not features().court_switcher:
        raise Http404
    schema = corpus_load_courts().get(court)
    path = (
        getattr(schema.branding, field)
        if schema and field in BRANDING_FIELDS
        else None
    )
    if path is None:
        raise Http404
    return FileResponse((COURTS_DIR / court / path).open("rb"))


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
    tabs = admin_tabs(request.user)
    if not tabs:
        raise PermissionDenied
    site = site_get()
    choices = dict.fromkeys(("fast", "assistant", "judge"), ())
    model_error = ""
    discovery_complete = False
    if "settings" in tabs:
        try:
            catalog = bedrock_catalog_get()
            discovery_complete = catalog.complete
            choices = {
                role: bedrock_model_choices(role=role, catalog=catalog)
                for role in choices
            }
            if not discovery_complete:
                model_error = _(
                    "Model discovery is incomplete. Some availability is unknown."
                )
            elif not any(choices.values()):
                model_error = _("No configured models are available.")
        except BedrockModelUnavailable as error:
            discovery_complete = False
            model_error = str(error)
    labels = {role: dict(options) for role, options in choices.items()}
    retained = {
        field: value
        for field in ("fast_model", "assistant_model", "judge_model")
        if (value := getattr(site, field))
        and value not in labels[field.removesuffix("_model")]
    }
    defaults = {}
    for role in ("fast", "assistant"):
        try:
            defaults[role] = labels[role][default_model(role, labels[role])]
        except BedrockModelUnavailable:
            defaults[role] = (
                _("Unavailable") if discovery_complete else _("Unknown")
            )
    return render(
        request,
        "pages/admin/index.html",
        {
            "bedrock_available": any(choices.values()),
            "model_choices": choices,
            "model_error": model_error,
            "retained_model_choices": retained,
            "unavailable_model_choices": retained
            if discovery_complete
            else {},
            "default_model_labels": defaults,
            "role_choices": role_choices(request.user),
            "jurisdiction_choices": JurisdictionLevel.choices,
            "state_choices": State.choices,
        },
    )
