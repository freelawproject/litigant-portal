from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db.models import Max
from django.utils.text import slugify

from litigant_portal.app.cache import TOPIC_LIST_CACHE_KEY
from litigant_portal.app.models import Topic
from litigant_portal.app.models.choices import VariableDataType

from .utils import busts_cache


def _topic_unique_slug(*, title: str) -> str:
    base = slugify(title)[:64] or "topic"
    slug, n = base, 2
    while Topic.objects.filter(slug=slug).exists():
        suffix = f"-{n}"
        slug, n = base[: 64 - len(suffix)] + suffix, n + 1
    return slug


@busts_cache(TOPIC_LIST_CACHE_KEY)
def topic_create(**fields) -> Topic:
    """Create a topic, appended to the display order."""
    last = Topic.objects.aggregate(m=Max("order"))["m"]
    return Topic.objects.create(
        slug=_topic_unique_slug(title=fields["title"]),
        order=0 if last is None else last + 1,
        **fields,
    )


@busts_cache(TOPIC_LIST_CACHE_KEY)
def topic_update(*, topic: Topic, **fields) -> Topic:
    """Update a topic's editable fields."""
    for name, value in fields.items():
        setattr(topic, name, value)
    topic.save(update_fields=[*fields, "updated_at"])
    return topic


@busts_cache(TOPIC_LIST_CACHE_KEY)
def topic_delete(*, topic: Topic) -> None:
    topic.delete()


def variable_value_validate(*, data_type: str, choices: list, value):
    """Check a raw value against a variable's data_type and choices.

    Pure and DB-free so both the answer-writing path and the corpus loader
    can call it. Returns the value unchanged when valid; None always passes
    (it clears the answer). Raises ValidationError otherwise.
    """
    if value is None:
        return None

    if data_type == VariableDataType.TEXT:
        if not isinstance(value, str):
            raise ValidationError("Must be text.")
    elif data_type == VariableDataType.NUMBER:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValidationError("Must be a number.")
    elif data_type == VariableDataType.BOOLEAN:
        if not isinstance(value, bool):
            raise ValidationError("Must be true or false.")
    elif data_type in (VariableDataType.DATE, VariableDataType.DATETIME):
        parser = (
            date.fromisoformat
            if data_type == VariableDataType.DATE
            else datetime.fromisoformat
        )
        try:
            parser(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"Must be a valid ISO {data_type}.") from exc
    elif data_type == VariableDataType.CHOICE and value not in {
        c["value"] for c in choices
    }:
        raise ValidationError("Must be one of the declared choices.")

    return value
