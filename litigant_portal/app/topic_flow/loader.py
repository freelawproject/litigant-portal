"""Load and validate a Topic Flow corpus YAML into a typed ``Corpus``.

``CorpusLoader.load(path)`` parses the file, runs Pydantic validation, then
runs the id-reference cross-checks Pydantic can't express (they span sibling
lists). Every failure mode — unreadable file, bad YAML, schema violation,
dangling reference — surfaces as a single ``CorpusValidationError`` carrying
the file path and the full list of problems, so an author sees everything at
once instead of fixing one error per run.
"""

from pathlib import Path

import yaml
from pydantic import ValidationError

from litigant_portal.app.topic_flow.schema import (
    Corpus,
    FactGatherSection,
    IcsOutput,
    ResourcesOutput,
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
            if isinstance(s, FactGatherSection)
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
        elif isinstance(section, ResourcesOutput):
            for ref in section.resource_ids:
                if ref not in resource_ids:
                    problems.append(
                        f"output {section.id!r} references unknown "
                        f"resource {ref!r}"
                    )
    return problems
