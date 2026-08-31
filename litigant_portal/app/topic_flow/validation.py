"""Validate submitted fact_gather answers against the corpus question defs.

Pure and DB-free, mirroring ``deadlines.py`` / ``contacts.py``. The Topic Flow
POST handler calls this before persisting so a litigant can't advance past a
fact_gather section with a missing ``required`` answer, a ``choice`` outside
the declared list, or a date that won't parse. Returns
``{question_id: [message]}``; an empty dict means the submission is valid.

The date check earns its place at this layer: answers persist typed, so an
unparseable date raises at the storage layer, and a soft-gate here turns
what would be a 500 into an inline "fix this" the litigant can act on.

Scoped to what was submitted: a fact_gather section POSTs only its own fields,
so a question id absent from ``submitted`` belongs to a section that wasn't
posted and is skipped — no upfront errors on sections the litigant hasn't
reached yet.
"""

from datetime import date

from django.utils.translation import gettext_lazy as _

from litigant_portal.app.topic_flow.schema import FactGatherSection

REQUIRED_ERROR = _("Please answer this before continuing.")
INVALID_CHOICE_ERROR = _("Choose one of the listed options.")
INVALID_DATE_ERROR = _("Enter the date as YYYY-MM-DD, like 2026-03-15.")


def _is_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_answers(corpus, submitted):
    """Return ``{question_id: [error]}`` for invalid submitted answers."""
    errors: dict[str, list] = {}
    for section in corpus.sections:
        if not isinstance(section, FactGatherSection):
            continue
        for question in section.questions:
            if question.id not in submitted:
                continue
            value = (submitted.get(question.id) or "").strip()
            if question.required and not value:
                errors[question.id] = [REQUIRED_ERROR]
            elif (
                question.type == "choice"
                and value
                and value not in (question.choices or [])
            ):
                errors[question.id] = [INVALID_CHOICE_ERROR]
            elif question.type == "date" and value and not _is_date(value):
                errors[question.id] = [INVALID_DATE_ERROR]
    return errors
