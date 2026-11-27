from litigant_portal.state.models import TopicFlow, TopicFlowInterviewVariable
from litigant_portal.state.selectors import variable_answer_list


def topic_flow_url_kwargs(flow: TopicFlow) -> dict[str, str] | None:
    """The ``court``/``topic``/``role`` kwargs the guided page reverses
    from, or None for a topic without a court: it predates its first sync,
    so its page has no URL yet. Reads the loaded topic; callers select it."""
    if not flow.topic.court:
        return None
    return {
        "court": flow.topic.court,
        "topic": flow.topic.slug,
        "role": flow.slug,
    }


def variable_answer_groups(*, identity, flow=None, answers=None) -> list[dict]:
    """
    An identity's answers, grouped for reading by interview page.

    With a flow, use its prefetched placements and the caller's projected
    answers. Otherwise, load applicable stored answers and use the first
    placement in (topic, flow, page, placement) order for stable grouping.

    Pages that place nothing this identity answered are skipped rather than
    rendered as empty headings, and answers with no placement collect in a
    final untitled group.

    The answer selector excludes cleared and out-of-schema answers.
    Flow callers supply answers already filtered by the projection.
    """
    if answers is None:
        answers = variable_answer_list(identity=identity, answered_only=True)
    if not answers:
        return []

    answer_by_variable = {a.variable_id: a for a in answers}
    placements = (
        [
            placement
            for page in flow.interview_pages.all()
            for placement in page.variables.all()
            if placement.variable_id in answer_by_variable
        ]
        if flow is not None
        else TopicFlowInterviewVariable.objects.filter(
            variable_id__in=answer_by_variable, page__flow__enabled=True
        )
        .select_related("page")
        .order_by(
            "page__flow__topic__order",
            "page__flow__topic__created_at",
            "page__flow__order",
            "page__flow__created_at",
            "page__order",
            "page__created_at",
            "order",
            "created_at",
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
