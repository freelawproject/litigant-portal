from dataclasses import dataclass
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.utils.text import slugify

from litigant_portal.app.cache import (
    COURT_SWITCHER_CHOICES_CACHE_KEY,
    TOPIC_FLOW_LIST_CACHE_KEY,
    TOPIC_LIST_CACHE_KEY,
)
from litigant_portal.app.models import (
    FlowViewState,
    Topic,
    TopicFlow,
    UserIdentity,
    Variable,
    VariableAnswer,
)
from litigant_portal.state.models import VariableDataType
from litigant_portal.state.reducer import reduce
from litigant_portal.state.rules import applicable_facts
from litigant_portal.state.selectors import state_snapshot
from litigant_portal.state.types import (
    ActionType,
    ConfirmFactsActionType,
    FactInputType,
    MarkViewedActionType,
    SetFactsActionType,
)

from .utils import busts_cache


def _topic_unique_slug(*, title: str) -> str:
    base = slugify(title)[:64] or "topic"
    slug, n = base, 2
    while Topic.objects.filter(slug=slug).exists():
        suffix = f"-{n}"
        slug, n = base[: 64 - len(suffix)] + suffix, n + 1
    return slug


@busts_cache(
    TOPIC_LIST_CACHE_KEY,
    TOPIC_FLOW_LIST_CACHE_KEY,
    COURT_SWITCHER_CHOICES_CACHE_KEY,
)
def topic_create(**fields) -> Topic:
    """Create a topic, appended to the display order."""
    last = Topic.objects.aggregate(m=Max("order"))["m"]
    return Topic.objects.create(
        slug=_topic_unique_slug(title=fields["title"]),
        order=0 if last is None else last + 1,
        **fields,
    )


@busts_cache(
    TOPIC_LIST_CACHE_KEY,
    TOPIC_FLOW_LIST_CACHE_KEY,
    COURT_SWITCHER_CHOICES_CACHE_KEY,
)
def topic_update(*, topic: Topic, **fields) -> Topic:
    """Update a topic's editable fields."""
    for name, value in fields.items():
        setattr(topic, name, value)
    topic.save(update_fields=[*fields, "updated_at"])
    return topic


@busts_cache(
    TOPIC_LIST_CACHE_KEY,
    TOPIC_FLOW_LIST_CACHE_KEY,
    COURT_SWITCHER_CHOICES_CACHE_KEY,
)
def topic_delete(*, topic: Topic) -> None:
    topic.delete()


def variable_value_validate(*, data_type: str, choices: list, value):
    """Check a raw value against a variable's data_type and choices.

    The one place that decides whether a value is legal, for both the
    answer-writing path and the corpus loader (``_variable_value_problem``
    in selectors/corpus.py adapts this to a message string). Pure and
    DB-free. ``choices`` is the stored shape, a list of {value, label}
    dicts. Returns the value unchanged when valid; None always passes (it
    clears the answer). Raises ValidationError otherwise, worded as a
    fragment so callers can embed it in a fuller sentence.
    """
    if value is None:
        return None

    if data_type == VariableDataType.NUMBER:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValidationError("must be a number")
    elif data_type == VariableDataType.BOOLEAN:
        if not isinstance(value, bool):
            raise ValidationError("must be true or false")
    elif data_type in (VariableDataType.DATE, VariableDataType.DATETIME):
        parser = (
            date.fromisoformat
            if data_type == VariableDataType.DATE
            else datetime.fromisoformat
        )
        try:
            parser(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                f"must be an ISO {data_type} string"
            ) from exc
    elif data_type == VariableDataType.CHOICE:
        values = [c["value"] for c in choices or []]
        if value not in values:
            raise ValidationError(f"must be one of {values}")
    elif not isinstance(value, str):
        raise ValidationError("must be a string")

    return value


@dataclass(frozen=True)
class StateChangeType:
    answers: dict[str, VariableAnswer]
    changed_names: set[str]
    value_changed_names: set[str]


@transaction.atomic
def _state_apply(
    *,
    identity: UserIdentity,
    action: ActionType,
    flow: TopicFlow | None = None,
) -> StateChangeType:
    """
    Serialize a domain transition and persist only its changed facts.

    Lock the owner, including for first writes where no answer row exists.
    Django assigns persisted timestamps; subsequent snapshots read those
    timestamps for confirmation and concurrency checks.
    """
    UserIdentity.objects.select_for_update().get(pk=identity.pk)
    answers = {
        answer.variable.name: answer
        for answer in VariableAnswer.objects.filter(
            identity=identity
        ).select_related("variable")
    }
    viewed = (
        FlowViewState.objects.filter(identity=identity, flow=flow)
        .values_list("viewed", flat=True)
        .first()
        if flow is not None
        else None
    )
    current_state = state_snapshot(
        identity=identity,
        flow=flow,
        answers=answers.values(),
        viewed=viewed,
    )
    variables = {}
    if isinstance(action, SetFactsActionType):
        variables = {
            variable.name: variable
            for variable in Variable.objects.filter(name__in=action.facts)
        }
        missing = sorted(set(action.facts) - variables.keys())
        if missing:
            raise Variable.DoesNotExist(
                f"No glossary variable named {missing}"
            )
        for name, fact in action.facts.items():
            variable = variables[name]
            variable_value_validate(
                data_type=variable.data_type,
                choices=variable.choices,
                value=fact.value,
            )
        action = action.model_copy(update={"at": timezone.now()})
    elif isinstance(action, ConfirmFactsActionType):
        applicable = applicable_facts(
            {
                name: a.value
                for name, a in answers.items()
                if a.variable.in_schema
            },
            {
                name: a.variable.condition
                for name, a in answers.items()
                if a.variable.in_schema
            },
        )
        action = action.model_copy(
            update={
                "names": tuple(
                    name for name in action.names if name in applicable
                )
            }
        )
    next_state = reduce(current_state, action)
    changed: set[str] = set()
    value_changed: set[str] = set()
    for name, fact in next_state.facts.items():
        previous = current_state.facts.get(name)
        if fact == previous:
            continue
        changed.add(name)
        if previous is None or previous.value != fact.value:
            value_changed.add(name)
        fields = fact.model_dump()
        if previous is None:
            answers[name] = VariableAnswer.objects.create(
                identity=identity, variable=variables[name], **fields
            )
            continue
        updated_fields = [
            field
            for field, value in fields.items()
            if value != getattr(previous, field)
        ]
        answer = answers[name]
        for field in updated_fields:
            setattr(answer, field, fields[field])
        answer.save(update_fields=updated_fields)
    if next_state.viewed != current_state.viewed:
        FlowViewState.objects.update_or_create(
            identity=identity,
            flow=flow,
            defaults={"viewed": next_state.viewed},
        )
    return StateChangeType(answers, changed, value_changed)


def variable_answer_set(
    *,
    identity,
    variable: Variable,
    value,
    reviewed: bool = False,
    evidence: dict[str, str | None] | None = None,
) -> VariableAnswer:
    """
    Upsert an identity's answer to a variable.

    Validate first. Unchanged values can gain missing evidence but keep
    existing evidence and their timestamp; only an explicit human
    confirmation can update reviewed. Changed values replace evidence and
    use the caller's reviewed status, defaulting to False for AI writes.
    Only reviewed answers may reach docassemble prefill.
    """
    change = _state_apply(
        identity=identity,
        action=SetFactsActionType(
            actor="human" if reviewed else "assistant",
            facts={
                variable.name: FactInputType(value=value, evidence=evidence)
            },
            at=timezone.now(),
        ),
    )
    return change.answers[variable.name]


def variable_answer_confirm(
    *, identity, names: list[str], as_of: datetime
) -> int:
    """Mark an identity's answers to ``names`` as human-reviewed.

    ``as_of`` is when the surface the person confirmed from read the
    answers; a row written after it shows a value the person never saw,
    so it stays unconfirmed. Returns how many rows changed;
    already-reviewed rows do not count. Cleared answers (value None) and
    out-of-schema variables are skipped: neither is a fact any surface
    shows, so there is nothing to confirm. Only ever called from a
    session-authenticated page view, never from an agent tool: reviewed
    answers reach the docassemble prefill, and the model must not confirm
    what it wrote itself.
    """
    change = _state_apply(
        identity=identity,
        action=ConfirmFactsActionType(
            actor="human", names=tuple(names), as_of=as_of
        ),
    )
    return len(change.changed_names)


def variable_answer_set_many(
    *, identity, values: dict, reviewed: bool = False
) -> int:
    """
    Upsert answers keyed by variable name; return how many were processed.

    Raises ``Variable.DoesNotExist`` if a name has no glossary row. That is
    a corpus-sync failure, not litigant input, so it must surface rather
    than drop the answer silently. All-or-nothing: one invalid value rolls
    the whole batch back.
    """
    _state_apply(
        identity=identity,
        action=SetFactsActionType(
            actor="human" if reviewed else "assistant",
            facts={
                name: FactInputType(value=value)
                for name, value in values.items()
            },
            at=timezone.now(),
        ),
    )
    return len(values)


def variable_answers_record(
    *, identity: UserIdentity, facts: dict[str, FactInputType]
) -> StateChangeType:
    """
    Save an assistant's valid facts as one unconfirmed batch.

    The tool reports invalid siblings before submitting this batch. The
    boundary revalidates against the current glossary under the owner lock.
    """
    if not facts:
        return StateChangeType({}, set(), set())
    return _state_apply(
        identity=identity,
        action=SetFactsActionType(
            actor="assistant", facts=facts, at=timezone.now()
        ),
    )


def topic_flow_section_viewed(
    *,
    identity: UserIdentity,
    flow: TopicFlow,
    component_id: str,
    signature: str,
) -> None:
    """
    Record a human Continue action using the server's component signature.

    The HTTP adapter must resolve the applicable component and its
    signature before calling this service, just as it establishes the
    identity for a fact write.
    """
    _state_apply(
        identity=identity,
        flow=flow,
        action=MarkViewedActionType(
            actor="human", component_id=component_id, signature=signature
        ),
    )
