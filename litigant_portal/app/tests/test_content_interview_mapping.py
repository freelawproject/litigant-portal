"""Drift guard: every mapped interview variable exists in the interview.

A preset variable skips its question and its validation, so a stale name is
dropped silently and a bad choice value prints onto a court form. Covers the
flows whose interview is versioned under ``docassemble/``. DB-free.

Skipped under ``make test``: the container image carries no interviews, only
``litigant_portal/``. CI runs tox against a full checkout, so the guard gates
merges there.
"""

import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import yaml

from litigant_portal.app.topic_flow.loader import CorpusLoader
from litigant_portal.app.topic_flow.prefill import interview_target
from litigant_portal.app.topic_flow.registry import (
    CONTENT_DIR,
    iter_corpus_paths,
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


def _interview_path(interview_url):
    """The versioned interview file a launch URL points at, if we have it."""
    reference = parse_qs(urlparse(interview_url).query).get("i", [])
    if not reference:
        return None
    file_name = reference[0].rsplit(":", 1)[-1]
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


def _mapped():
    """(content file, question id, interview variable, interview path)."""
    for path in iter_corpus_paths(CONTENT_DIR):
        target = interview_target(CorpusLoader.load(path))
        if target is None:
            continue
        interview_url, mapping = target
        interview_path = _interview_path(interview_url)
        if interview_path is None:
            continue
        for question_id, variable in mapping.items():
            yield path.name, question_id, variable, interview_path


def _handoff_interviews():
    """(content file, interview path) per interview a flow hands off to.

    Every flow with an interview_url, mapped or not: the handoff creates a
    session either way.
    """
    seen = {}
    for path in iter_corpus_paths(CONTENT_DIR):
        target = interview_target(CorpusLoader.load(path))
        if target is None:
            continue
        interview_path = _interview_path(target[0])
        if interview_path is not None:
            seen.setdefault(interview_path, path.name)
    return [(name, path) for path, name in seen.items()]


MAPPED = list(_mapped())
INTERVIEWS = _handoff_interviews()


def test_the_nd_name_change_flows_are_actually_being_checked():
    # A broken URL-to-file match would empty every parametrized guard below.
    assert len(MAPPED) >= 9


@pytest.mark.parametrize(
    ("file_name", "question_id", "variable", "interview_path"),
    MAPPED,
    ids=[f"{f}:{q}" for f, q, _v, _p in MAPPED],
)
def test_mapped_variable_exists_in_the_interview(
    file_name, question_id, variable, interview_path
):
    fields = _fields(interview_path)
    assert variable in fields, (
        f"{file_name} maps '{question_id}' to '{variable}', which "
        f"{interview_path.name} does not ask"
    )


@pytest.mark.parametrize(
    ("file_name", "question_id", "variable", "interview_path"),
    MAPPED,
    ids=[f"{f}:{q}" for f, q, _v, _p in MAPPED],
)
def test_a_mapped_checkbox_variable_is_never_prefilled(
    file_name, question_id, variable, interview_path
):
    # checkboxes is a DADict: a plain value corrupts the answer.
    entry = _fields(interview_path).get(variable, {})
    assert entry.get("datatype") != "checkboxes", (
        f"{file_name} maps '{question_id}' to the checkboxes variable "
        f"'{variable}'"
    )


def test_mapped_choice_values_agree_with_the_interview():
    for file_name, question_id, variable, interview_path in MAPPED:
        corpus = CorpusLoader.load(CONTENT_DIR / file_name)
        question = next(
            (
                q
                for section in corpus.sections
                if section.kind == "fact_gather"
                for q in section.questions
                if q.id == question_id
            ),
            None,
        )
        if question is None or question.type != "choice":
            continue
        declared = _fields(interview_path)[variable].get("choices") or []
        allowed = {
            value
            for choice in declared
            for value in (
                choice.values() if isinstance(choice, dict) else [choice]
            )
        }
        assert set(question.choices) <= allowed, (
            f"{file_name} '{question_id}' offers values "
            f"{set(question.choices) - allowed} that {interview_path.name} "
            f"does not accept for '{variable}'"
        )


@pytest.mark.parametrize(
    ("file_name", "interview_path"),
    INTERVIEWS,
    ids=[p.name for _f, p in INTERVIEWS],
)
def test_interview_enables_multi_user_from_an_initial_block(
    file_name, interview_path
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
        f"{interview_path.name} (handed off from {file_name}) does not set "
        "multi_user = True in an initial code block"
    )


@pytest.mark.parametrize(
    ("file_name", "interview_path"),
    INTERVIEWS,
    ids=[p.name for _f, p in INTERVIEWS],
)
def test_interview_never_sets_multi_user_as_a_bare_key(
    file_name, interview_path
):
    # A bare `multi_user: True` key throws DASourceError on load.
    assert not any(
        "multi_user" in block for block in _blocks(interview_path)
    ), f"{interview_path.name} sets multi_user as a key, not as initial code"
