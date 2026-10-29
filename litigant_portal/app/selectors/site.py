from django.core.cache import cache

from litigant_portal.app.cache import (
    CONTACT_LIST_CACHE_KEY,
    RESOURCE_LIST_CACHE_KEY,
    SITE_CACHE_KEY,
)
from litigant_portal.app.models import Contact, Resource, Site
from litigant_portal.app.models.choices import ContactKind
from litigant_portal.app.selectors.bedrock import (
    bedrock_available_models,
    bedrock_model_target,
)
from lp_agent.adapters.bedrock_models import (
    BedrockModelUnavailable,
    ResolvedBedrockModel,
    default_model,
)


def site_get() -> Site:
    """The singleton settings row, served from cache."""
    site = cache.get(SITE_CACHE_KEY)
    if site is None:
        site = Site.objects.get()
        cache.set(SITE_CACHE_KEY, site, timeout=None)
    return site


def _cached_list(key: str, model) -> list:
    rows = cache.get(key)
    if rows is None:
        rows = list(model.objects.all())
        cache.set(key, rows, timeout=None)
    return rows


# Neither cached list is scoped by court: the rows belong to the Site
# singleton's one court, and a multi-court sync (CORPUS_COURT unset) pools
# every court's rows into them. ``court`` narrows a list to the rows one
# court's sync stamped, for a page that serves that court's URL.


def _court_rows(rows: list, court: str | None) -> list:
    if court is None:
        return rows
    return [row for row in rows if row.court == court]


def contact_list(*, court: str | None = None) -> list[Contact]:
    """The court's contacts, in display order, served from cache."""
    return _court_rows(_cached_list(CONTACT_LIST_CACHE_KEY, Contact), court)


def contact_help_list() -> list[Contact]:
    """The contacts the help page lists: those with a help kind, grouped in
    ``ContactKind`` order, each kind in display order."""
    rank = {kind: i for i, kind in enumerate(ContactKind.values)}
    return sorted(
        (c for c in contact_list() if c.kind in rank),
        key=lambda c: rank[c.kind],
    )


def resource_list(*, court: str | None = None) -> list[Resource]:
    """The court's resources, in display order, served from cache."""
    return _court_rows(_cached_list(RESOURCE_LIST_CACHE_KEY, Resource), court)


def site_get_model_target(
    *, role: str, required: frozenset[str] = frozenset({"text"})
) -> ResolvedBedrockModel:
    """
    Resolve a site's role preference to one concrete invocation target.
    """
    if model := getattr(site_get(), f"{role}_model"):
        return bedrock_model_target(model=model, required=required)
    if role == "judge":
        raise BedrockModelUnavailable("Judging is disabled.")
    available = bedrock_available_models(required=required)
    return available[default_model(role, available)]
