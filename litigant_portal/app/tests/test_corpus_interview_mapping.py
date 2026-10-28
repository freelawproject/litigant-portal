"""Drift guard: every mapped interview variable exists in the interview.

A preset variable skips its question and its validation, so a stale name is
dropped silently and a bad choice value prints onto a court form. Covers the
corpus flows whose interview is versioned under ``docassemble/``. DB-free.

Skipped under ``make test``: the container image carries no interviews, only
``litigant_portal/``. CI runs tox against a full checkout, so the guard gates
merges there.
"""

import re
from pathlib import Path

import pytest
import yaml

from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.selectors.corpus import (
    corpus_load_flows,
    corpus_load_variables,
)

INTERVIEW_DIR = Path(__file__).resolve().parents[3] / "docassemble"

pytestmark = pytest.mark.skipif(
    not INTERVIEW_DIR.is_dir(),
    reason=f"no interviews at {INTERVIEW_DIR} (container image)",
)

# Keys sitting beside a field's ``Label: variable`` entry, whose values can
# themselves look like identifiers ("datatype: date").
_MODIFIERS = {
    "required",
    "datatype",
    "choices",
    "hint",
    "help",
    "default",
    "min",
    "max",
    "maxlength",
    "rows",
    "show if",
    "validate",
    "note",
    "css class",
}


def _interview_path(reference):
    """The versioned interview file a reference points at, if we have it."""
    file_name = reference.rsplit(":", 1)[-1].rsplit("/", 1)[-1]
    matches = list(INTERVIEW_DIR.glob(f"*/{file_name}"))
    return matches[0] if len(matches) == 1 else None


def _blocks(interview_path):
    """Every mapping block in an interview, in file order."""
    return [
        block
        for block in yaml.safe_load_all(
            interview_path.read_text(encoding="utf-8")
        )
        if isinstance(block, dict)
    ]


def _fields(interview_path):
    """``{variable: field block}`` for every field the interview asks."""
    fields = {}
    for block in _blocks(interview_path):
        for entry in block.get("fields") or []:
            if not isinstance(entry, dict):
                continue
            for key, value in entry.items():
                if key in _MODIFIERS or not isinstance(value, str):
                    continue
                fields[value] = entry
    return fields


def _handoffs():
    """(flow label, handoff, interview path) per flow handing off to an
    interview we have."""
    for slugs, flow in corpus_load_flows().items():
        if flow.handoff is None:
            continue
        interview_path = _interview_path(flow.handoff.interview_reference)
        if interview_path is not None:
            yield "/".join(slugs), flow.handoff, interview_path


def _mapped():
    """(flow label, variable name, interview variable, interview path)."""
    for label, handoff, interview_path in _handoffs():
        for name, variable in handoff.interview_prefill.items():
            yield label, name, variable, interview_path


def _handoff_interviews():
    """(flow label, interview path) per interview a flow hands off to.

    Every flow with an interview reference, mapped or not: the handoff creates a
    session either way.
    """
    seen = {}
    for label, _handoff, interview_path in _handoffs():
        seen.setdefault(interview_path, label)
    return [(label, path) for path, label in seen.items()]


MAPPED = list(_mapped())
INTERVIEWS = _handoff_interviews()


def test_the_nd_name_change_flows_are_actually_being_checked():
    # A broken URL-to-file match would empty every parametrized guard below.
    assert len(MAPPED) >= 9


@pytest.mark.parametrize(
    ("label", "name", "variable", "interview_path"),
    MAPPED,
    ids=[f"{f}:{q}" for f, q, _v, _p in MAPPED],
)
def test_mapped_variable_exists_in_the_interview(
    label, name, variable, interview_path
):
    fields = _fields(interview_path)
    assert variable in fields, (
        f"{label} maps '{name}' to '{variable}', which "
        f"{interview_path.name} does not ask"
    )


@pytest.mark.parametrize(
    ("label", "name", "variable", "interview_path"),
    MAPPED,
    ids=[f"{f}:{q}" for f, q, _v, _p in MAPPED],
)
def test_a_mapped_checkbox_variable_is_never_prefilled(
    label, name, variable, interview_path
):
    # checkboxes is a DADict: a plain value corrupts the answer.
    entry = _fields(interview_path).get(variable, {})
    assert entry.get("datatype") != "checkboxes", (
        f"{label} maps '{name}' to the checkboxes variable '{variable}'"
    )


def test_mapped_choice_values_agree_with_the_interview():
    glossary = corpus_load_variables()
    for label, name, variable, interview_path in MAPPED:
        glossary_variable = glossary[name]
        if glossary_variable.data_type != VariableDataType.CHOICE:
            continue
        offered = {choice.value for choice in glossary_variable.choices}
        declared = _fields(interview_path)[variable].get("choices") or []
        allowed = {
            value
            for choice in declared
            for value in (
                choice.values() if isinstance(choice, dict) else [choice]
            )
        }
        assert offered <= allowed, (
            f"{label} '{name}' offers values {offered - allowed} that "
            f"{interview_path.name} does not accept for '{variable}'"
        )


@pytest.mark.parametrize(
    ("label", "interview_path"),
    INTERVIEWS,
    ids=[p.name for _f, p in INTERVIEWS],
)
def test_interview_enables_multi_user_from_an_initial_block(
    label, interview_path
):
    # The one prerequisite with no fallback: without it the resume link cannot
    # decrypt the session, so the litigant gets an error rather than a plain
    # interview.
    initial_code = "\n".join(
        block.get("code") or ""
        for block in _blocks(interview_path)
        if block.get("initial")
    )
    assert re.search(r"multi_user\s*=\s*True", initial_code), (
        f"{interview_path.name} (handed off from {label}) does not set "
        "multi_user = True in an initial code block"
    )


@pytest.mark.parametrize(
    ("label", "interview_path"),
    INTERVIEWS,
    ids=[p.name for _f, p in INTERVIEWS],
)
def test_interview_never_sets_multi_user_as_a_bare_key(label, interview_path):
    # A bare `multi_user: True` key throws DASourceError on load.
    assert not any(
        "multi_user" in block for block in _blocks(interview_path)
    ), f"{interview_path.name} sets multi_user as a key, not as initial code"
