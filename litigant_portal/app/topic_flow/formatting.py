from __future__ import annotations

from typing import TYPE_CHECKING

from django.core.exceptions import ObjectDoesNotExist
from django.utils import formats
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.translation import gettext as _

from litigant_portal.app.formatting import format_long_date

if TYPE_CHECKING:
    from litigant_portal.state.models import VariableAnswer


def format_answer(answer: VariableAnswer) -> str:
    """
    Format a stored answer for guided pages, review cards, and chat.

    Unknown choices and unparseable dates retain their stored values so
    the user can still see and correct them.
    """
    from litigant_portal.state.models import VariableDataType

    value = answer.value
    if isinstance(value, bool):
        return _("Yes") if value else _("No")
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if value is None:
        return ""

    raw = str(value)
    try:
        variable = answer.variable
    except ObjectDoesNotExist:
        return raw

    if variable.data_type == VariableDataType.CHOICE:
        return next(
            (
                choice["label"]
                for choice in variable.choices
                if choice["value"] == value
            ),
            raw,
        )
    if variable.data_type == VariableDataType.DATE:
        parsed = parse_date(raw)
        return format_long_date(parsed) if parsed else raw
    if variable.data_type == VariableDataType.DATETIME:
        parsed = parse_datetime(raw)
        return (
            formats.date_format(parsed, "DATETIME_FORMAT") if parsed else raw
        )
    return raw
