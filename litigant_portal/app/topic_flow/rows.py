"""Build the guided page from TopicFlow rows.

The sibling of ``renderer.py`` for the ``TOPIC_FLOW_SOURCE=corpus`` path: it
reads the rows ``sync_corpus`` writes instead of the ``content/`` registry,
and produces the same ``RenderedSection`` list, so the page template does not
know which path built it. Pure: callers pass the prefetched rows in, and
nothing here touches the database or the request.

The flow's ``layout`` orders the page. A section key renders as an info
section anchored on that key, so chat citations can link to it. The
``interview`` block renders one fact-gather form per interview page, anchored
``interview-1``, ``interview-2``, ... in page order; the other block names
(``LAYOUT_BLOCKS``) render as placeholders until #1017 fills them in.

A gated variable (``asked_when``) is asked only while the stored answer to
its gate matches, the same rule the review-facts tool applies. There is no
client-side show/hide: the litigant saves the gate, the page reloads, and the
gated fields appear.
"""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.selectors.corpus import default_layout
from litigant_portal.app.services.topic_flow import variable_value_validate
from litigant_portal.app.topic_flow.renderer import (
    NEVER_PREFILL,
    RenderedSection,
)
from litigant_portal.app.topic_flow.validation import (
    INVALID_CHOICE_ERROR,
    INVALID_DATE_ERROR,
    REQUIRED_ERROR,
)

INVALID_NUMBER_ERROR = _("Enter a number, like 3 or 2.5.")
# Digits with an optional decimal part. ``float()`` is wider (``nan``,
# ``inf``, ``1e3``, ``1_000``), and the first two break the JSON column.
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")

_TEMPLATE_DIR = "cotton/molecules"

# The form template's field kinds: an <input type> for the plain ones, and
# the two it renders as a <select>.
_QUESTION_TYPES = {
    VariableDataType.TEXT: "text",
    VariableDataType.DATE: "date",
    VariableDataType.DATETIME: "datetime-local",
    VariableDataType.NUMBER: "number",
    VariableDataType.CHOICE: "choice",
    VariableDataType.BOOLEAN: "boolean",
}

# A select, not a checkbox: a checkbox cannot say "not answered yet", and
# ``required`` on one would force "yes". The values are what coerce_value
# reads back.
BOOLEAN_CHOICES = [
    {"value": "true", "label": _("Yes")},
    {"value": "false", "label": _("No")},
]

BLOCK_HEADINGS = {
    "interview": _("Your answers"),
    "packet": _("Your forms"),
    "calendar": _("Your deadlines"),
    "contacts": _("Who to contact"),
    "resources": _("Resources"),
}

PLACEHOLDER_TEXT = _("This part of the page is coming soon.")
GATE_HINT = _(
    "Depending on your answer, more questions may appear after you save."
)


def section_anchor(section, number: int) -> str:
    """The section's key, or ``section-N`` for a row without one (the schema
    requires a key, but an older or admin-edited row may lack it)."""
    return section.key or f"section-{number}"


def flow_layout(flow, sections) -> list[str]:
    """The stored layout, or every section key then the blocks when empty."""
    return list(flow.layout) or default_layout(
        section_anchor(section, number)
        for number, section in enumerate(sections, 1)
    )


def flow_pages(flow) -> list[tuple]:
    """``[(page, [variable, ...]), ...]`` in page then placement order, read
    from the rows ``topic_flow_find`` prefetched."""
    return [
        (page, [placed.variable for placed in page.variables.all()])
        for page in flow.interview_pages.all()
    ]


def flow_variable_names(pages) -> list[str]:
    """Every variable the pages place, plus the gates they depend on: the
    names whose answers the page needs to decide what to show."""
    names = []
    for _page, variables in pages:
        for variable in variables:
            names.append(variable.name)
            if variable.asked_when is not None:
                names.append(variable.asked_when.name)
    return list(dict.fromkeys(names))


def asked_names(pages, answers) -> list[str]:
    """Every variable currently asked, across all pages in order. The POST
    keys the entry view accepts."""
    return [
        variable.name
        for _page, variables in pages
        for variable in variables
        if variable.is_asked(answers)
    ]


def stale_gated_names(pages, answers, valid) -> list[str]:
    """Gated variables whose gate will not match once ``valid`` is written,
    and that have an answer to clear."""
    after = {
        name: value
        for name, value in {**answers, **valid}.items()
        if value is not None
    }
    return [
        variable.name
        for _page, variables in pages
        for variable in variables
        if variable.asked_when is not None
        and not variable.is_asked(after)
        and variable.name in after
    ]


def _form_value(value) -> str:
    """A stored (typed) answer as the string the form field shows."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def gate_names(pages) -> set[str]:
    """The variables that gate another one, across every page: a gate's
    dependents may sit on a later page than the gate itself."""
    return {
        variable.asked_when.name
        for _page, variables in pages
        for variable in variables
        if variable.asked_when is not None
    }


def page_questions(variables, answers, gates=frozenset()) -> list[dict]:
    """One question dict per asked variable, in placement order, in the shape
    the fact-gather template reads. ``gates`` is ``gate_names`` of the whole
    flow."""
    # A gated field appears only after its gate is saved and the page
    # reloads, so the gate question says so (WCAG 3.3.2).
    questions = []
    for variable in variables:
        if not variable.is_asked(answers):
            continue
        name = variable.name
        protected = name in NEVER_PREFILL
        saved = protected and name in answers
        stored = answers.get(name, variable.default)
        help_text = variable.help_text
        if name in gates:
            help_text = f"{help_text} {GATE_HINT}" if help_text else GATE_HINT
        questions.append(
            {
                "id": name,
                "label": variable.label or name,
                "type": _QUESTION_TYPES[variable.data_type],
                # The browser's default step rejects decimals, which the
                # store allows, so a number field takes any step.
                "step": (
                    "any"
                    if variable.data_type == VariableDataType.NUMBER
                    else ""
                ),
                # A protected field renders blank even when stored, so
                # ``required`` would block every later save of its page.
                "required": variable.required and not saved,
                "choices": (
                    BOOLEAN_CHOICES
                    if variable.data_type == VariableDataType.BOOLEAN
                    else variable.choices
                ),
                "help_text": help_text,
                # Same leak guard as the content renderer: a protected field
                # renders blank and gets the clear checkbox instead (#638).
                "value": "" if protected else _form_value(stored),
                "saved": saved,
                "errors": [],
                "autofocus": False,
            }
        )
    return questions


def render_flow(
    flow, sections, pages, answers, errors=None
) -> list[RenderedSection]:
    """One ``RenderedSection`` per layout entry, in layout order; the
    ``interview`` entry expands to one per page."""
    by_key = {
        section_anchor(section, number): section
        for number, section in enumerate(sections, 1)
    }
    gates = gate_names(pages)
    rendered = []
    for name in flow_layout(flow, sections):
        if name in by_key:
            rendered.append(_render_info(name, by_key[name]))
        elif name == "interview":
            rendered.extend(
                _render_page(number, page, variables, answers, gates)
                for number, (page, variables) in enumerate(pages, 1)
            )
        elif name in BLOCK_HEADINGS:
            rendered.append(_render_placeholder(name))
        # else: a name the schema would have rejected; leave it out
    if errors:
        _apply_errors(rendered, errors)
    return rendered


def _apply_errors(rendered, errors):
    """Put each inline error on its question and focus the first one, as
    ``render_section`` does for the content path (WCAG 2.4.3 / 3.3.1)."""
    focused = False
    for section in rendered:
        for question in section.context.get("questions", ()):
            question["errors"] = errors.get(question["id"], [])
            if question["errors"] and not focused:
                question["autofocus"] = True
                focused = True


def _render_page(number, page, variables, answers, gates):
    return RenderedSection(
        anchor_id=f"interview-{number}",
        heading=page.title,
        template=f"{_TEMPLATE_DIR}/flow_section_fact_gather.html",
        context={
            "description": page.description,
            "questions": page_questions(variables, answers, gates),
        },
    )


def _render_info(anchor, section):
    return RenderedSection(
        anchor_id=anchor,
        heading=section.heading,
        template=f"{_TEMPLATE_DIR}/flow_section_info.html",
        context={"body": section.content},
    )


def _render_placeholder(block):
    return RenderedSection(
        anchor_id=block,
        heading=BLOCK_HEADINGS[block],
        template=f"{_TEMPLATE_DIR}/flow_section_placeholder.html",
        context={"text": PLACEHOLDER_TEXT},
    )


def coerce_value(variable, raw: str):
    """The form string as the typed value the glossary stores.

    Strips; blank is None (clears the answer). A number becomes int, or
    float when it has a decimal part (the store accepts both, and another
    writer may have stored a float the form must round-trip), a boolean
    select's ``true``/``false`` becomes bool, everything else stays a
    string. Raises ValueError when the string cannot be read as the type.
    """
    value = raw.strip()
    if not value:
        return None
    if variable.data_type == VariableDataType.NUMBER:
        if not _NUMBER.match(value):
            raise ValueError(f"not a number: {value!r}")
        return float(value) if "." in value else int(value)
    if variable.data_type == VariableDataType.BOOLEAN:
        if value not in ("true", "false"):
            raise ValueError(f"not a boolean: {value!r}")
        return value == "true"
    return value


def validate_answers(variables, submitted, keep=frozenset()) -> dict:
    """``{name: [error]}`` for invalid submitted answers, over glossary rows.

    The sibling of ``validation.validate_answers``. Scoped to what was
    submitted: a page POSTs only its own fields, so a variable absent from
    ``submitted`` is skipped. ``keep`` names the protected fields with a
    stored answer: they render blank, so a blank there means "keep what is
    stored", not a missing required answer. The type check is
    ``variable_value_validate``, the same rule the answer-writing service
    applies, so nothing passes here that the store would reject.
    """
    errors: dict[str, list] = {}
    for variable in variables:
        name = variable.name
        if name not in submitted:
            continue
        blank = not submitted[name].strip()
        if variable.required and blank and name not in keep:
            errors[name] = [REQUIRED_ERROR]
            continue
        try:
            value = coerce_value(variable, submitted[name])
            variable_value_validate(
                data_type=variable.data_type,
                choices=variable.choices,
                value=value,
            )
        except (ValueError, ValidationError):
            errors[name] = [_type_error(variable.data_type)]
    return errors


def _type_error(data_type):
    if data_type == VariableDataType.NUMBER:
        return INVALID_NUMBER_ERROR
    if data_type in (VariableDataType.DATE, VariableDataType.DATETIME):
        return INVALID_DATE_ERROR
    return INVALID_CHOICE_ERROR


def submitted_section_anchor(pages, submitted_names) -> str | None:
    """The ``interview-N`` anchor of the page that owns the submitted
    answers, for the redirect after POST; None when nothing matches."""
    submitted = set(submitted_names)
    for number, (_page, variables) in enumerate(pages, 1):
        if any(variable.name in submitted for variable in variables):
            return f"interview-{number}"
    return None
