from django.core.cache import cache

from litigant_portal.app.cache import TOPIC_LIST_CACHE_KEY
from litigant_portal.app.models import (
    Topic,
    TopicFlow,
    TopicFlowInterviewVariable,
    VariableAnswer,
)


def topic_list() -> list[Topic]:
    """Topics in display order, served from cache."""
    topics = cache.get(TOPIC_LIST_CACHE_KEY)
    if topics is None:
        topics = list(Topic.objects.all())
        cache.set(TOPIC_LIST_CACHE_KEY, topics, timeout=None)
    return topics


def topic_get(*, topic_id) -> Topic:
    """A single topic (raises Topic.DoesNotExist)."""
    return Topic.objects.get(id=topic_id)


def topic_flow_list() -> list[TopicFlow]:
    """Enabled flows with their topics, in topic order then flow order."""
    return list(
        TopicFlow.objects.filter(enabled=True)
        .select_related("topic")
        .order_by("topic__order", "topic__created_at", "order", "created_at")
    )


def topic_flow_find(*, topic_slug: str, flow_slug: str) -> TopicFlow | None:
    """The enabled flow at (topic_slug, flow_slug) with its whole content
    graph prefetched, or None."""
    return (
        TopicFlow.objects.filter(
            topic__slug=topic_slug, slug=flow_slug, enabled=True
        )
        .select_related("topic")
        .prefetch_related(
            "sections",
            "links",
            "deadlines__offset_from",
            "form_conditions__form",
            "form_conditions__variable",
            "interview_pages__variables__variable__asked_when",
        )
        .first()
    )


def variable_answer_list(*, identity) -> list[VariableAnswer]:
    """An identity's answers, ordered by variable name.

    Answers to variables the corpus no longer names (``in_schema=False``)
    are left out: sync keeps those rows so a migration can move them, but
    no form references them, so no surface should show them.
    """
    return list(
        VariableAnswer.objects.filter(
            identity=identity, variable__in_schema=True
        )
        .select_related("variable")
        .order_by("variable__name")
    )


def variable_answer_map(*, identity, names: list[str]) -> dict:
    """{variable_name: value} for the given names; names with no answer are omitted.

    A cleared answer (value None) counts as no answer: this map feeds
    prefill and templates, where an absent key must stay absent rather
    than fill a blank. Excludes out-of-schema variables, as
    ``variable_answer_list`` does.
    """
    return dict(
        VariableAnswer.objects.filter(
            identity=identity,
            variable__name__in=names,
            variable__in_schema=True,
            value__isnull=False,
        ).values_list("variable__name", "value")
    )


def briefcase_groups(*, identity) -> list[dict]:
    """An identity's answers, grouped for reading by interview page.

    Grouping comes from each answered variable's own placement
    (``TopicFlowInterviewVariable``), not from an active flow: the chat page
    resolves no flow server-side, so placement is the only grouping available
    without a model change. A variable placed on more than one page is grouped
    under the first placement in (topic, flow, page, placement) order, which
    keeps the grouping stable across requests.

    Pages that place nothing this identity answered are skipped rather than
    rendered as empty headings, and answers with no placement collect in a
    final untitled group.

    Cleared answers (``value`` None) and out-of-schema variables are left out,
    matching ``variable_answer_map``: a cleared fact is not a fact, and no
    surface should show a variable the corpus no longer names.
    """
    answers = list(
        VariableAnswer.objects.filter(
            identity=identity, variable__in_schema=True, value__isnull=False
        )
        .select_related("variable")
        .order_by("variable__name")
    )
    if not answers:
        return []

    answer_by_variable = {a.variable_id: a for a in answers}
    placements = (
        TopicFlowInterviewVariable.objects.filter(
            variable_id__in=answer_by_variable
        )
        .select_related("page")
        .order_by(
            "page__flow__topic__order",
            "page__flow__order",
            "page__order",
            "order",
        )
    )

    # Walking placements in that order builds both the page sequence and the
    # sequence within each page, so neither needs a second sort.
    grouped: dict = {}
    placed: set = set()
    for placement in placements:
        if placement.variable_id in placed:
            continue
        placed.add(placement.variable_id)
        grouped.setdefault(placement.page, []).append(
            answer_by_variable[placement.variable_id]
        )

    groups = [
        {"title": page.title, "answers": page_answers}
        for page, page_answers in grouped.items()
    ]
    unplaced = [a for a in answers if a.variable_id not in placed]
    if unplaced:
        groups.append({"title": "", "answers": unplaced})
    return groups
