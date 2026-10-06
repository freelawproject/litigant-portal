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
