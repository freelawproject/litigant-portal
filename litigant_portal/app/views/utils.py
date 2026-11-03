from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth.password_validation import (
    CommonPasswordValidator,
    MinimumLengthValidator,
    NumericPasswordValidator,
    UserAttributeSimilarityValidator,
    get_default_password_validators,
)
from django.http import Http404, JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.timesince import timesince
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, ngettext

from litigant_portal.app.features import features
from litigant_portal.app.models.chat_engine import USER_CHAT_THREAD_TYPE
from litigant_portal.app.permissions import Tier
from litigant_portal.app.selectors.chat_engine import chat_thread_list
from litigant_portal.app.selectors.topic_flow import (
    topic_flow_find,
    topic_flow_list,
    topic_flow_url_kwargs,
    variable_answer_cleared_names,
    variable_answer_groups,
    variable_answer_map,
)
from litigant_portal.app.selectors.user import user_assignable_roles


def has_identity(request) -> bool:
    """Whether this visitor already has an identity worth reading.

    ``request.identity`` resolves lazily by minting a session and a
    ``UserIdentity`` row, so an unguarded read banks one per anonymous hit,
    crawlers included. Every read-only surface checks this first.
    """
    return bool(request.user.is_authenticated or request.session.session_key)


def topic_flow_row_get(court, topic, role, *, graph=True):
    """The enabled ``TopicFlow`` row behind a ``/t/<court>/<topic>/<role>/``
    URL; ``graph`` is passed to ``topic_flow_find``. The row's topic must
    carry the URL's court, which must also be the instance's court when
    ``CORPUS_COURT`` is set. Raises ``Http404`` on any miss."""
    if settings.CORPUS_COURT is not None and court != settings.CORPUS_COURT:
        raise Http404(f"No Topic Flow for {court}/{topic}/{role}")
    flow = topic_flow_find(
        topic_slug=topic, flow_slug=role, court=court, graph=graph
    )
    if flow is None:
        raise Http404(f"No Topic Flow for {court}/{topic}/{role}")
    return flow


def topic_flow_row_answers(request, names: list[str]) -> dict:
    """``{variable_name: value}`` for the given names, for the page and its
    downloads. Reads through the glossary, so a fact the assistant stored
    shows up here too. Empty for a visitor with no identity yet."""
    return _answer_map(request, names)


def topic_flow_row_cleared_names(request, names: list[str]) -> set[str]:
    """The given names this visitor has cleared, so the rows page shows a
    blank there instead of the glossary default. Empty without an identity."""
    if not has_identity(request):
        return set()
    return set(
        variable_answer_cleared_names(identity=request.identity, names=names)
    )


def topic_flow_reviewed_answers(request, names: list[str]) -> dict:
    """``{question_id: value}`` for confirmed answers only, for the prefill."""
    return _answer_map(request, names, reviewed_only=True)


def _answer_map(request, names, *, reviewed_only=False) -> dict:
    if not has_identity(request):
        return {}
    return variable_answer_map(
        identity=request.identity, names=names, reviewed_only=reviewed_only
    )


def topic_flow_cards() -> list[dict]:
    """``{title, description, icon, url}`` per enabled flow with a guided
    page: the home grid's cards (#1068).

    One card per flow, however many a topic has, so merging a topic's flows
    (#930) or splitting one changes the cards with no code change. A topic
    with no court has no page yet, so its flows get no card.
    """
    cards = []
    for flow in topic_flow_list():
        page = topic_flow_url_kwargs(flow)
        if page is not None:
            cards.append(
                {
                    "title": flow.name,
                    "description": flow.topic.description,
                    "icon": flow.topic.icon,
                    "url": reverse("pages:topic_flow", kwargs=page),
                }
            )
    return cards


def briefcase_answers(request) -> list[dict]:
    """The visitor's stored facts, grouped for the briefcase panel.

    Empty for a visitor with no identity yet, which renders as the panel's
    empty state rather than an absent context key.
    """
    if not has_identity(request):
        return []
    return variable_answer_groups(identity=request.identity)


def activity_threads(request) -> list[dict]:
    """The visitor's chats, serialized for a static Activity list.

    Mirrors the assistant thread-list API's shape so the home page's
    server-rendered region shows the same rows the chat page's live
    sidebar does. Empty for a visitor with no identity yet.
    """
    if not has_identity(request):
        return []
    threads = []
    for thread in chat_thread_list(
        identity=request.identity, thread_type=USER_CHAT_THREAD_TYPE
    ):
        last_at = thread.last_message_at or thread.updated_at
        threads.append(
            {
                "id": str(thread.id),
                "description": thread.description,
                "snippet": (thread.snippet or "")[:500],
                "last_at": last_at,
                "when": _activity_when(last_at),
            }
        )
    return threads


def _activity_when(last_at) -> str:
    """A thread's age as the chat sidebar's timeSince() words it, so the two
    lists agree — timesince alone says "0 minutes" under a minute."""
    if timezone.now() - last_at < timedelta(minutes=1):
        return _("just now")
    return _("%(when)s ago") % {"when": timesince(last_at)}


def _perm_required(codename: str):
    """Build a JSON guard requiring ``codename``."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.has_perm(codename):
                return JsonResponse({"error": _("Forbidden")}, status=403)
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


manage_site_required = _perm_required("app.manage_site")
"""JSON guard: requires ``app.manage_site`` (held by FLP Staff and,
implicitly, superusers)."""


def can_manage_app_users(user) -> bool:
    """Whether ``user`` reaches app user management on this deployment.

    Off where the ``user_admin`` feature is off (plain prod), so the Court
    Admins group grants nothing there (#1043).
    """
    return features().user_admin and user.has_perm("app.manage_app_users")


ADMIN_TABS = ["settings", "users", "knowledge", "simulate"]


def admin_tabs(user) -> list[str]:
    """The admin dashboard tabs ``user`` may open; empty means no dashboard.

    A Court Admin gets the Users tab alone: the Site and Topics rows are
    FLP's, and ``sync_corpus`` overwrites them on every deploy anyway.
    """
    if user.has_perm("app.manage_site"):
        return ADMIN_TABS
    if can_manage_app_users(user):
        return ["users"]
    return []


def app_user_admin_required(view):
    """JSON guard for the app user account actions: not found where the
    feature is off, forbidden without ``app.manage_app_users``."""

    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not features().user_admin:
            return JsonResponse({"error": _("Not found")}, status=404)
        if not request.user.has_perm("app.manage_app_users"):
            return JsonResponse({"error": _("Forbidden")}, status=403)
        return view(request, *args, **kwargs)

    return wrapped


ROLE_LABELS = {
    Tier.SUPERUSER: gettext_lazy("Superuser"),
    Tier.FLP_STAFF: gettext_lazy("FLP Staff"),
    Tier.COURT_ADMIN: gettext_lazy("Court Admin"),
    Tier.APP_USER: gettext_lazy("App user"),
}


def role_value(tier: Tier) -> str:
    """How a role travels in forms and JSON: ``court_admin``."""
    return tier.name.lower()


def role_parse(value: str) -> Tier | None:
    """The assignable role a form value names, or None. Superuser is never
    one."""
    for tier in Tier:
        if tier < Tier.SUPERUSER and role_value(tier) == value:
            return tier
    return None


def role_choices(user) -> list[tuple[str, str]]:
    """``(value, label)`` for every role ``user`` may give an account."""
    return [
        (role_value(t), ROLE_LABELS[t])
        for t in user_assignable_roles(viewer=user)
    ]


# What each validator rules out, as "Can't be ___", in the order said.
_PASSWORD_EXCLUSIONS = [
    (NumericPasswordValidator, gettext_lazy("all numbers")),
    (CommonPasswordValidator, gettext_lazy("a common password")),
    (UserAttributeSimilarityValidator, gettext_lazy("similar to email")),
]


def _or_list(items: list[str]) -> str:
    """``a``, ``a or b``, ``a, b, or c``."""
    if len(items) < 3:
        return _(" or ").join(items)
    return _("%(items)s, or %(last)s") % {
        "items": ", ".join(items[:-1]),
        "last": items[-1],
    }


def password_rule() -> str:
    """The password rules every new-password field states up front, built
    from the configured validators so they match what ``validate_password``
    enforces on submit: the length, then what the password can't be. A
    validator we haven't phrased adds Django's own help text, so no rule
    goes unsaid."""
    validators = get_default_password_validators()
    sentences = [
        ngettext(
            "At least %(count)d character.",
            "At least %(count)d characters.",
            v.min_length,
        )
        % {"count": v.min_length}
        for v in validators
        if isinstance(v, MinimumLengthValidator)
    ]
    exclusions = [
        str(phrase)
        for kind, phrase in _PASSWORD_EXCLUSIONS
        if any(isinstance(v, kind) for v in validators)
    ]
    if exclusions:
        sentences.append(
            _("Can't be %(exclusions)s.")
            % {"exclusions": _or_list(exclusions)}
        )
    known = (
        MinimumLengthValidator,
        *(kind for kind, _phrase in _PASSWORD_EXCLUSIONS),
    )
    sentences += [
        v.get_help_text() for v in validators if not isinstance(v, known)
    ]
    return " ".join(sentences)
