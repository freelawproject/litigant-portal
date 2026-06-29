"""Validate submitted fact_gather answers against the corpus question defs.

Pure and DB-free, mirroring ``deadlines.py`` / ``contacts.py``. The Topic Flow
POST handler calls this before persisting so a litigant can't advance past a
fact_gather section with a missing ``required`` answer or a ``choice`` outside
the declared list — the two holes the schema models and the renderer surfaces
but the handler used to ignore. Returns ``{question_id: [message]}``; an empty
dict means the submission is valid.

Scoped to what was submitted: a fact_gather section POSTs only its own fields,
so a question id absent from ``submitted`` belongs to a section that wasn't
posted and is skipped — no upfront errors on sections the litigant hasn't
reached yet.
"""

from django.utils.translation import gettext_lazy as _

from litigant_portal.app.topic_flow.schema import FactGatherSection

REQUIRED_ERROR = _("Please answer this before continuing.")
INVALID_CHOICE_ERROR = _("Choose one of the listed options.")


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
    return errors
