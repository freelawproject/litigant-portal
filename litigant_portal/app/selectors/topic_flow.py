from django.core.cache import cache

from litigant_portal.app.cache import TOPIC_LIST_CACHE_KEY
from litigant_portal.app.models import (
    Topic,
    TopicFlow,
    TopicFlowDeadline,
    TopicFlowField,
    TopicFlowFieldGroup,
    TopicFlowForm,
    TopicFlowLink,
    UserIdentity,
)


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


def topic_flow_fields(*, flow: TopicFlow) -> list[TopicFlowField]:
    """The flow's fields across all its groups, in interview order.

    Not the ``flow.fields`` related manager: that sorts flow-wide by field
    order alone, which interleaves groups. Interview order composes group
    order with field order, and iterating the two related managers keeps
    any prefetch the caller set up.
    """
    return [
        field
        for group in flow.field_groups.all()
        for field in group.fields.all()
    ]


def topic_flow_form_get(*, form_id) -> TopicFlowForm:
    """A single flow form (raises DoesNotExist)."""
    return TopicFlowForm.objects.get(id=form_id)


def topic_flow_deadline_get(*, deadline_id) -> TopicFlowDeadline:
    """A single flow deadline (raises DoesNotExist)."""
    return TopicFlowDeadline.objects.get(id=deadline_id)


def topic_flow_field_group_get(*, group_id) -> TopicFlowFieldGroup:
    """A single flow field group (raises DoesNotExist)."""
    return TopicFlowFieldGroup.objects.get(id=group_id)


def topic_flow_field_get(*, field_id) -> TopicFlowField:
    """A single flow field (raises DoesNotExist)."""
    return TopicFlowField.objects.get(id=field_id)


def topic_flow_link_get(*, link_id) -> TopicFlowLink:
    """A single flow link (raises DoesNotExist)."""
    return TopicFlowLink.objects.get(id=link_id)


def topic_flow_slug_taken(*, topic: Topic, slug: str, exclude_id=None) -> bool:
    """Whether ``topic`` already has a flow with this slug — the unique
    pair behind ``/t/<topic>/<flow>/``."""
    flows = topic.flows.filter(slug=slug)
    if exclude_id is not None:
        flows = flows.exclude(id=exclude_id)
    return flows.exists()


def topic_flow_date_field_get(
    *, flow: TopicFlow, name: str
) -> TopicFlowField | None:
    """One of ``flow``'s date/datetime fields by name, or ``None``.

    A deadline counts forward from a date the litigant supplies, so only
    these types can anchor one.
    """
    return TopicFlowField.objects.filter(
        group__flow=flow,
        name=name,
        data_type__in=[
            TopicFlowField.DataType.DATE,
            TopicFlowField.DataType.DATETIME,
        ],
    ).first()


def topic_flow_field_name_taken(
    *, flow: TopicFlow, name: str, exclude_id=None
) -> bool:
    """Whether ``flow`` already has a field with this name. Names are the
    answer keys and PDF-template variables, so they're unique per flow."""
    fields = TopicFlowField.objects.filter(group__flow=flow, name=name)
    if exclude_id is not None:
        fields = fields.exclude(id=exclude_id)
    return fields.exists()


def topic_flow_get_public(*, topic_slug: str, flow_slug: str) -> TopicFlow:
    """A live flow by topic and flow slug (raises TopicFlow.DoesNotExist),
    with children prefetched for the flow page. Draft flows are invisible here."""
    return (
        TopicFlow.objects.filter(
            topic__slug=topic_slug, slug=flow_slug, enabled=True
        )
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
