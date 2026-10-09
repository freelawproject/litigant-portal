"""Evaluate corpus ``when`` gates against a visitor's answers.

Pure and DB-free, like ``deadlines.py``: ``evaluate`` decides one
``Condition``; ``applying`` walks the corpus in order and returns which
sections and questions currently apply, plus the answers restricted to the
questions being asked.

Stale facts are derived, never stored. An answer to a question that is no
longer asked (its section or its own gate stopped applying) stays in the
store but drops out of ``applying_answers``, so every later gate sees it as
missing. Switch the path back and it applies again without re-entering.
"""

from dataclasses import dataclass, field

from litigant_portal.app.topic_flow.schema import QUESTION_SECTIONS


@dataclass(frozen=True)
class Applying:
    section_ids: frozenset[str]
    question_ids: frozenset[str]
    applying_answers: dict = field(default_factory=dict)

    def section(self, section) -> bool:
        return section.id in self.section_ids

    def question(self, question) -> bool:
        return question.id in self.question_ids


def evaluate(condition, answers) -> bool:
    """True when ``condition`` holds for ``answers`` (``{question_id: value}``).

    ``None`` always holds. A missing or blank fact fails every leaf except
    ``answered: false``, so nothing gated on a fact shows before that fact is
    answered.
    """
    if condition is None:
        return True
    if condition.all is not None:
        return all(evaluate(child, answers) for child in condition.all)
    if condition.any is not None:
        return any(evaluate(child, answers) for child in condition.any)
    if condition.not_ is not None:
        return not evaluate(condition.not_, answers)

    value = answers.get(condition.fact)
    answered = value is not None and value != ""
    if condition.answered is not None:
        return answered == condition.answered
    if not answered:
        return False
    if condition.equals is not None:
        return value == condition.equals
    if condition.not_equals is not None:
        return value != condition.not_equals
    return value in condition.in_


def applying(corpus, answers) -> Applying:
    """Which sections and questions apply for ``answers``, in corpus order.

    A question is asked when its section applies and its own gate holds.
    Each gate is evaluated against the applying answers gathered so far, so
    an answer to a hidden question counts as missing for everything after it.
    """
    section_ids = set()
    question_ids = set()
    applying_answers = {}
    for section in corpus.sections:
        if not evaluate(section.when, applying_answers):
            continue
        section_ids.add(section.id)
        if not isinstance(section, QUESTION_SECTIONS):
            continue
        for question in section.questions:
            if not evaluate(question.when, applying_answers):
                continue
            question_ids.add(question.id)
            if question.id in answers:
                applying_answers[question.id] = answers[question.id]
    return Applying(
        section_ids=frozenset(section_ids),
        question_ids=frozenset(question_ids),
        applying_answers=applying_answers,
    )


@dataclass(frozen=True)
class Revealed:
    """How far down the page a visitor has unlocked.

    ``section_ids`` are the applying sections shown, in corpus order.
    ``waiting_on`` is the id of the last one when it holds an unanswered
    gate, so the page can say more steps follow; ``None`` when nothing is
    held back.
    """

    section_ids: list[str]
    waiting_on: str | None


def _conditions(corpus):
    """Every ``when`` in the corpus: sections, questions, screener outcomes,
    packet forms and deadlines."""
    for deadline in corpus.deadlines:
        yield deadline.when
    for section in corpus.sections:
        yield section.when
        for question in getattr(section, "questions", []):
            yield question.when
        for outcome in getattr(section, "outcomes", []):
            yield outcome.when
        for form in getattr(section, "forms", []):
            yield getattr(form, "when", None)


def _facts(condition):
    if condition is None:
        return
    if condition.fact:
        yield condition.fact
    for child in (*(condition.all or ()), *(condition.any or ())):
        yield from _facts(child)
    yield from _facts(condition.not_)


def gate_facts(corpus) -> frozenset[str]:
    """The question ids some ``when`` reads: answering one can change what
    the page shows, so an unanswered one holds back what follows it."""
    return frozenset(
        fact for condition in _conditions(corpus) for fact in _facts(condition)
    )


def revealed(corpus, applies: Applying) -> Revealed:
    """The applying sections up to and including the first one that holds
    an unanswered gate question, the way A2J Author reveals an interview.

    Answering that gate reveals sections up to the next one. Changing an
    earlier gate re-runs this from the top, so whatever follows it is
    recomputed rather than remembered.
    """
    gates = gate_facts(corpus)
    shown = []
    for section in corpus.sections:
        if not applies.section(section):
            continue
        shown.append(section.id)
        unanswered_gate = any(
            applies.question(question)
            and question.id in gates
            and applies.applying_answers.get(question.id) in (None, "")
            for question in getattr(section, "questions", [])
        )
        if unanswered_gate:
            return Revealed(section_ids=shown, waiting_on=section.id)
    return Revealed(section_ids=shown, waiting_on=None)


def replaced_gate_answer(corpus, stored, saved) -> str | None:
    """The gate question whose existing answer ``saved`` replaces with a
    different one, such as switching the path from renter to marina, or
    ``None``.

    A first answer to a gate reveals what was promised to follow it, so it
    isn't a change worth telling anyone about; replacing one changes steps
    the visitor may already have read.
    """
    gates = gate_facts(corpus)
    return next(
        (
            question_id
            for question_id, value in saved.items()
            if question_id in gates
            and stored.get(question_id) not in (None, "")
            and stored.get(question_id) != value
        ),
        None,
    )
