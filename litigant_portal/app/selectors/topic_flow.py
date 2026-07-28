from django.core.cache import cache

from litigant_portal.app.models import (
    Topic,
    TopicFlow,
    TopicFlowDeadline,
    TopicFlowForm,
    TopicFlowLink,
    UserIdentity,
)

TOPIC_LIST_CACHE_KEY = "topic_list"


def topic_list() -> list[Topic]:
    """Topics in display order, with flows and their children prefetched, served from cache."""
    topics = cache.get(TOPIC_LIST_CACHE_KEY)
    if topics is None:
        topics = list(
            Topic.objects.prefetch_related(
                "flows__sections",
                "flows__field_groups__fields",
                "flows__links",
                "flows__deadlines__offset_from",
                "flows__forms__mappings",
            )
        )
        cache.set(TOPIC_LIST_CACHE_KEY, topics, timeout=None)
    return topics


def topic_get(*, topic_id) -> Topic:
    """A single topic (raises Topic.DoesNotExist)."""
    return Topic.objects.get(id=topic_id)


def topic_flow_get(*, flow_id) -> TopicFlow:
    """A single flow (raises TopicFlow.DoesNotExist)."""
    return TopicFlow.objects.get(id=flow_id)


def topic_flow_form_get(*, form_id) -> TopicFlowForm:
    """A single flow form (raises DoesNotExist)."""
    return TopicFlowForm.objects.get(id=form_id)


def topic_flow_deadline_get(*, deadline_id) -> TopicFlowDeadline:
    """A single flow deadline (raises DoesNotExist)."""
    return TopicFlowDeadline.objects.get(id=deadline_id)


def topic_flow_link_get(*, link_id) -> TopicFlowLink:
    """A single flow link (raises DoesNotExist)."""
    return TopicFlowLink.objects.get(id=link_id)


def topic_flow_get_public(*, topic_slug: str, flow_slug: str) -> TopicFlow:
    """A flow by topic and flow slug (raises TopicFlow.DoesNotExist),
    with children prefetched for the flow page."""
    return (
        TopicFlow.objects.filter(topic__slug=topic_slug, slug=flow_slug)
        .prefetch_related(
            "sections",
            "field_groups__fields",
            "links",
            "deadlines__offset_from",
            "forms__mappings",
        )
        .get()
    )


def topic_flow_answer_values(
    *, identity: UserIdentity, flow: TopicFlow
) -> dict[str, object]:
    """The identity's stored answers for ``flow``, field name -> value."""
    return {
        answer.field.name: answer.value
        for answer in identity.flow_answers.filter(
            field__group__flow=flow
        ).select_related("field")
        if answer.value is not None
    }
