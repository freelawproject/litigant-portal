from __future__ import annotations

from collections.abc import Iterator, Mapping
from graphlib import TopologicalSorter
from typing import assert_never

from pydantic import Field, JsonValue, TypeAdapter

from litigant_portal.state.types import StateModelType


class EqualsConditionType(StateModelType):
    fact: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    equals: bool | int | float | str


class AllConditionType(StateModelType):
    all: list[ConditionType] = Field(min_length=1)


class AnyConditionType(StateModelType):
    any: list[ConditionType] = Field(min_length=1)


class NotConditionType(StateModelType):
    not_: ConditionType = Field(alias="not")


type ConditionType = (
    EqualsConditionType
    | AllConditionType
    | AnyConditionType
    | NotConditionType
)

AllConditionType.model_rebuild()
AnyConditionType.model_rebuild()
NotConditionType.model_rebuild()
_condition_adapter = TypeAdapter(ConditionType | None)


def parse_condition(value: JsonValue) -> ConditionType | None:
    return _condition_adapter.validate_python(value)


def condition_leaves(
    condition: ConditionType | None,
) -> Iterator[EqualsConditionType]:
    match condition:
        case EqualsConditionType():
            yield condition
        case AllConditionType():
            for child in condition.all:
                yield from condition_leaves(child)
        case AnyConditionType():
            for child in condition.any:
                yield from condition_leaves(child)
        case NotConditionType():
            yield from condition_leaves(condition.not_)
        case None:
            return
        case _:
            assert_never(condition)


def condition_names(condition: ConditionType | None) -> set[str]:
    return {leaf.fact for leaf in condition_leaves(condition)}


def applicable_facts(
    facts: Mapping[str, JsonValue],
    conditions: Mapping[str, ConditionType | None],
) -> dict[str, JsonValue]:
    """
    Evaluate dependencies first so hidden facts stay unknown downstream.

    Corpus validation rejects cycles. Missing prerequisites are left out,
    including references absent from this snapshot's glossary.
    """
    graph = {
        name: condition_names(condition)
        for name, condition in conditions.items()
    }
    applicable: dict[str, JsonValue] = {}
    for name in TopologicalSorter(graph).static_order():
        value = facts.get(name)
        if value is not None and condition_matches(
            conditions.get(name), applicable
        ):
            applicable[name] = value
    return applicable


def condition_matches(
    condition: ConditionType | None, facts: Mapping[str, JsonValue]
) -> bool:
    """
    Only a true condition permits content; unknown prerequisites do not.

    Callers supply applicable facts. An absent or cleared fact remains
    unknown under negation, so unanswered gates cannot reveal a path.
    """
    return condition is None or _evaluate(condition, facts) is True


def _evaluate(
    condition: ConditionType, facts: Mapping[str, JsonValue]
) -> bool | None:
    match condition:
        case EqualsConditionType():
            value = facts.get(condition.fact)
            return None if value is None else value == condition.equals
        case AllConditionType():
            values = [_evaluate(child, facts) for child in condition.all]
            if False in values:
                return False
            return None if None in values else True
        case AnyConditionType():
            values = [_evaluate(child, facts) for child in condition.any]
            if True in values:
                return True
            return None if None in values else False
        case NotConditionType():
            value = _evaluate(condition.not_, facts)
            return None if value is None else not value
        case _:
            assert_never(condition)
