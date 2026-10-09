"""Load and validate a Topic Flow corpus YAML into a typed ``Corpus``.

``CorpusLoader.load(path)`` parses the file, runs Pydantic validation, then
runs the id-reference cross-checks Pydantic can't express (they span sibling
lists), including that every ``when`` gate names a question declared earlier
with values that question allows. Every failure mode — unreadable file, bad
YAML, schema violation, dangling reference — surfaces as a single
``CorpusValidationError`` carrying the file path and the full list of
problems, so an author sees everything at once instead of fixing one error
per run.
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from litigant_portal.app.topic_flow.schema import (
    QUESTION_SECTIONS,
    Corpus,
    IcsOutput,
    PacketOutput,
    ResourcesOutput,
    ScreenerSection,
    VcfOutput,
)


class CorpusValidationError(Exception):
    """A corpus file could not be loaded. Carries the path + all problems."""

    def __init__(self, path, problems):
        self.path = Path(path)
        self.problems = list(problems)
        detail = "\n  - ".join(self.problems)
        super().__init__(f"Invalid corpus {self.path}:\n  - {detail}")


class CorpusLoader:
    @staticmethod
    def load(path) -> Corpus:
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CorpusValidationError(path, [f"cannot read file: {exc}"])

        try:
            raw = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            raise CorpusValidationError(path, [f"YAML parse error: {exc}"])

        if not isinstance(raw, dict):
            raise CorpusValidationError(path, ["top level must be a mapping"])

        try:
            corpus = Corpus.model_validate(raw)
        except ValidationError as exc:
            raise CorpusValidationError(path, _schema_problems(exc))

        cross = _cross_reference_problems(corpus)
        if cross:
            raise CorpusValidationError(path, cross)
        return corpus


def _schema_problems(exc: ValidationError) -> list[str]:
    """Flatten a Pydantic ValidationError into ``loc: message`` lines."""
    problems = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"])
        problems.append(f"{loc}: {err['msg']}" if loc else err["msg"])
    return problems


def _cross_reference_problems(corpus: Corpus) -> list[str]:
    """Check id uniqueness and that every id-reference resolves."""
    problems = []

    def _collect(ids, kind):
        seen = set()
        for value in ids:
            if value in seen:
                problems.append(f"duplicate {kind} id: {value!r}")
            seen.add(value)
        return seen

    contact_ids = _collect([c.id for c in corpus.contacts], "contact")
    deadline_ids = _collect([d.id for d in corpus.deadlines], "deadline")
    resource_ids = _collect([r.id for r in corpus.resources], "resource")
    _collect([s.id for s in corpus.sections], "section")

    question_ids = _collect(
        [
            q.id
            for s in corpus.sections
            if isinstance(s, QUESTION_SECTIONS)
            for q in s.questions
        ],
        "question",
    )

    # A deadline is computed from a gathered date — offset_from must name a
    # fact_gather question.
    for deadline in corpus.deadlines:
        if deadline.offset_from not in question_ids:
            problems.append(
                f"deadline {deadline.id!r} offset_from "
                f"{deadline.offset_from!r} is not a fact_gather question id"
            )

    # Output sections reference corpus-level definitions by id.
    for section in corpus.sections:
        if isinstance(section, IcsOutput):
            for ref in section.deadline_ids:
                if ref not in deadline_ids:
                    problems.append(
                        f"output {section.id!r} references unknown "
                        f"deadline {ref!r}"
                    )
        elif isinstance(section, VcfOutput):
            for ref in section.contact_ids:
                if ref not in contact_ids:
                    problems.append(
                        f"output {section.id!r} references unknown "
                        f"contact {ref!r}"
                    )
        elif isinstance(section, PacketOutput):
            if section.interview_prefill and not section.interview_reference:
                problems.append(
                    f"output {section.id!r} has interview_prefill but no "
                    "interview_reference to send it to"
                )
            for ref in section.interview_prefill:
                if ref not in question_ids:
                    problems.append(
                        f"output {section.id!r} prefills {ref!r}, which is "
                        "not a fact_gather question id"
                    )
        elif isinstance(section, ResourcesOutput):
            for ref in section.resource_ids:
                if ref not in resource_ids:
                    problems.append(
                        f"output {section.id!r} references unknown "
                        f"resource {ref!r}"
                    )

    problems.extend(_condition_problems(corpus))
    return problems


def _leaves(condition):
    """Yield the leaf conditions under ``condition``, itself included."""
    if condition.all is not None:
        for child in condition.all:
            yield from _leaves(child)
    elif condition.any is not None:
        for child in condition.any:
            yield from _leaves(child)
    elif condition.not_ is not None:
        yield from _leaves(condition.not_)
    else:
        yield condition


def _condition_problems(corpus: Corpus) -> list[str]:
    """Check every ``when`` names an earlier question with legal values.

    Walks the sections in corpus order. A gate may only name a question
    declared before it (a question's own gate sees the earlier questions of
    its section; a screener's outcomes see the screener's own questions), so
    one forward pass evaluates everything and there is no cycle to detect.
    Deadlines are corpus-level and are resolved after every section, so they
    may name any question. A screener's ``fact`` must be an earlier choice
    question and every outcome ``value`` one of its choices.
    """
    problems = []
    declared: dict[str, object] = {}

    def _check(owner, condition, visible):
        for leaf in _leaves(condition):
            question = visible.get(leaf.fact)
            if question is None:
                problems.append(
                    f"{owner} when: fact {leaf.fact!r} is not a question "
                    "declared earlier in the corpus"
                )
                continue
            if question.type != "choice":
                continue
            values = leaf.equals, leaf.not_equals, *(leaf.in_ or [])
            for value in values:
                if value is not None and value not in question.choices:
                    problems.append(
                        f"{owner} when: {value!r} is not a choice of "
                        f"{leaf.fact!r}"
                    )

    for section in corpus.sections:
        if section.when is not None:
            _check(f"section {section.id!r}", section.when, declared)
        if isinstance(section, ScreenerSection):
            # Outcomes see the screener's own questions; check them after
            # those are declared, below.
            outcome_gates = [
                (f"screener {section.id!r} outcome {o.value!r}", o.when)
                for o in section.outcomes
            ]
        else:
            outcome_gates = []
        if isinstance(section, PacketOutput):
            for form in section.forms:
                if form.when is not None:
                    _check(
                        f"output {section.id!r} form {form.name!r}",
                        form.when,
                        declared,
                    )
        if isinstance(section, QUESTION_SECTIONS):
            for question in section.questions:
                if question.when is not None:
                    _check(
                        f"question {question.id!r}", question.when, declared
                    )
                declared[question.id] = question
        for owner, gate in outcome_gates:
            _check(owner, gate, declared)
        if isinstance(section, ScreenerSection):
            problems.extend(_screener_problems(section, declared))

    for deadline in corpus.deadlines:
        if deadline.when is not None:
            _check(f"deadline {deadline.id!r}", deadline.when, declared)
    return problems


def _screener_problems(section, declared) -> list[str]:
    """``declared`` holds every question up to and including the screener's."""
    owner = f"screener {section.id!r}"
    fact = declared.get(section.fact)
    problems = []
    if fact is None or fact.id in {q.id for q in section.questions}:
        problems.append(
            f"{owner} fact {section.fact!r} is not a question declared "
            "earlier in the corpus"
        )
    elif fact.type != "choice":
        problems.append(f"{owner} fact {section.fact!r} is not a choice")
    else:
        for outcome in section.outcomes:
            if outcome.value not in fact.choices:
                problems.append(
                    f"{owner} outcome {outcome.value!r} is not a choice of "
                    f"{section.fact!r}"
                )
    return problems
