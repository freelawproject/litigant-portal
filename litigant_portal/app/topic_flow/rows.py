"""Build the guided page from TopicFlow rows.

Reads the rows ``sync_corpus`` writes and produces the ``RenderedSection``
list the page template renders. Pure: callers pass the prefetched rows in,
and nothing here touches the database or the request.

The flow's ``layout`` orders the page. A section key renders as an info
section anchored on that key, so chat citations can link to it. The
``interview`` block renders one fact-gather form per interview page, anchored
``interview-1``, ``interview-2``, ... in page order. The ``packet`` block
lists the flow's forms whose condition holds against the stored answers,
with the docassemble handoff when the flow has one and the environment
serves it; the ``calendar`` block its deadlines, each computed from the
stored answer to its source variable; the ``contacts`` and ``resources``
blocks list the court's whole ``Contact`` and ``Resource`` lists in stored
order. A block with nothing to show is skipped.

A gated variable (``asked_when``) is asked only while the stored answer to
its gate matches, the same rule the review-facts tool applies. There is no
client-side show/hide: the litigant saves the gate, the page reloads, and the
gated fields appear.
"""

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.models.topic_flow import condition_holds
from litigant_portal.app.selectors.corpus import default_layout
from litigant_portal.app.services.docassemble import interview_launch_url
from litigant_portal.app.services.topic_flow import variable_value_validate
from litigant_portal.app.topic_flow.contacts import contact_dicts
from litigant_portal.app.topic_flow.deadlines import (
    deadline_date,
    deadline_display,
)
from litigant_portal.app.topic_flow.resources import resource_dicts


@dataclass(frozen=True)
class RenderedSection:
    """One page section: a template path plus a flat, fully-resolved context
    dict, so the page template stays logic-free."""

    anchor_id: str
    heading: str
    template: str
    context: dict


REQUIRED_ERROR = _("Please answer this before continuing.")
INVALID_CHOICE_ERROR = _("Choose one of the listed options.")
INVALID_DATE_ERROR = _("Enter the date as YYYY-MM-DD, like 2026-03-15.")

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


def private_names(pages) -> set[str]:
    """The placed variables the glossary marks private: the page's protected
    set, rendered blank whatever is stored."""
    return {
        variable.name
        for _page, variables in pages
        for variable in variables
        if variable.is_private
    }


def flow_variable_names(pages, form_conditions=(), deadlines=()) -> list[str]:
    """Every variable the pages place, plus the gates they depend on, the
    variables the packet's conditions read and the deadlines' source dates:
    the names whose answers the page needs to decide what to show. A
    condition's or a deadline's variable may be asked on no page of this
    flow and stored by the chat."""
    names = []
    for _page, variables in pages:
        for variable in variables:
            names.append(variable.name)
            if variable.asked_when is not None:
                names.append(variable.asked_when.name)
    for condition in form_conditions:
        if condition.variable is not None:
            names.append(condition.variable.name)
    names.extend(deadline.offset_from.name for deadline in deadlines)
    return list(dict.fromkeys(names))


def flow_deadlines(deadlines, answers) -> list[dict]:
    """``{id, label, description, date}`` per TopicFlowDeadline row, in
    stored order, the shape ``deadline_display`` and ``ics_artifact`` take.
    ``id`` is the row's ``ref`` (its authored key)."""
    return [
        {
            "id": deadline.ref,
            "label": deadline.label,
            "description": deadline.description,
            "date": deadline_date(
                deadline.offset_days, deadline.offset_from.name, answers
            ),
        }
        for deadline in deadlines
    ]


def form_condition_holds(condition, answers) -> bool:
    """Whether a packet entry shows: always without a variable; ``equals``
    when the stored answer is the value; ``not_equals`` when it is anything
    else, unanswered included."""
    if condition.variable is None:
        return True
    return condition_holds(
        answers, condition.variable.name, condition.value, condition.operator
    )


def packet_forms(form_conditions, answers) -> list[dict]:
    """``{name, url}`` per form whose condition holds, in stored order."""
    return [
        {"name": condition.form.name, "url": condition.form.url}
        for condition in form_conditions
        if form_condition_holds(condition, answers)
    ]


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
    """Gated variables whose gate is written by ``valid`` and will not match
    afterwards, and that have an answer to clear. A gate this POST does not
    touch leaves its dependents alone: the assistant may store a dependent
    before the gate is answered, and an unrelated save must not erase it."""
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
        and variable.asked_when.name in valid
        and not variable.is_asked(after)
        and variable.name in after
    ]


def _form_value(variable, value) -> str:
    """A stored (typed) answer as the string the form field shows.

    A date input displays one ISO form and shows blank for any other the
    store accepts (a basic ``20260315``, seconds, an offset), and a blank
    is erased on the next save of its page. So dates are reformatted; a
    datetime-local input has no zone, so an offset is dropped.

    A value that doesn't parse (stored before the glossary made the
    variable temporal) renders as stored, the way the briefcase shows it.

    A float is written out in full: ``str()`` gives ``1e-05`` for a small
    one, which the number rule rejects on the next save.
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return format(Decimal(repr(value)), "f")
    raw = str(value)
    try:
        if variable.data_type == VariableDataType.DATE:
            return date.fromisoformat(raw).isoformat()
        if variable.data_type == VariableDataType.DATETIME:
            parsed = datetime.fromisoformat(raw).replace(tzinfo=None)
            return parsed.isoformat(timespec="minutes")
    except ValueError:
        pass
    return raw


def restore_unchanged(variables, submitted, answers, valid) -> dict:
    """``valid`` with each answer the litigant left as the form showed it
    put back to its stored value.

    The form string is narrower than the store: a datetime input drops
    the zone and seconds, a number input the float type. Writing the
    posted string back would quietly rewrite an answer the litigant never
    touched, so an unchanged field re-saves what is stored. The row is
    still written, so it is marked reviewed. A private field renders blank,
    so a blank there is skipped upstream and a typed value is never
    "unchanged".
    """
    restored = {}
    for name, value in valid.items():
        variable = variables[name]
        if (
            name in answers
            and not variable.is_private
            and submitted[name].strip() == _form_value(variable, answers[name])
        ):
            value = answers[name]
        restored[name] = value
    return restored


def gate_names(pages) -> set[str]:
    """The variables that gate another one, across every page: a gate's
    dependents may sit on a later page than the gate itself."""
    return {
        variable.asked_when.name
        for _page, variables in pages
        for variable in variables
        if variable.asked_when is not None
    }


def page_questions(
    variables, answers, gates=frozenset(), cleared=frozenset()
) -> list[dict]:
    """One question dict per asked variable, in placement order, in the shape
    the fact-gather template reads. ``gates`` is ``gate_names`` of the whole
    flow; ``cleared`` names the variables the litigant blanked, which must
    not fall back to the glossary default."""
    # A gated field appears only after its gate is saved and the page
    # reloads, so the gate question says so (WCAG 3.3.2).
    questions = []
    for variable in variables:
        if not variable.is_asked(answers):
            continue
        name = variable.name
        protected = variable.is_private
        saved = protected and name in answers
        default = None if name in cleared else variable.default
        stored = answers.get(name, default)
        help_text = variable.help_text
        if name in gates:
            help_text = f"{help_text} {GATE_HINT}" if help_text else GATE_HINT
        questions.append(
            {
                "id": name,
                # The authored question is the wording the litigant is
                # asked; the label names the fact in the briefcase.
                "label": variable.question or variable.label or name,
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
                # The leak guard for a shared terminal, read from the
                # glossary row so the set can't drift from the corpus: a
                # private field renders blank and gets the clear checkbox
                # instead (#638).
                "value": "" if protected else _form_value(variable, stored),
                "saved": saved,
                "errors": [],
                "autofocus": False,
            }
        )
    return questions


def render_flow(
    flow,
    sections,
    pages,
    answers,
    errors=None,
    cleared=frozenset(),
    *,
    form_conditions=(),
    deadlines=(),
    contacts=(),
    resources=(),
    court="",
    topic="",
    role="",
) -> list[RenderedSection]:
    """One ``RenderedSection`` per layout entry, in layout order; the
    ``interview`` entry expands to one per page. ``cleared`` is passed to
    ``page_questions``. ``form_conditions`` and ``deadlines`` are the flow's
    rows, ``contacts`` and ``resources`` the court's; the URL parts name the
    flow for the download and interview links."""
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
                _render_page(number, page, variables, answers, gates, cleared)
                for number, (page, variables) in enumerate(pages, 1)
            )
        elif name == "packet":
            forms = packet_forms(form_conditions, answers)
            # The row's handoff AND a configured docassemble, else a plain
            # form list.
            interview = bool(
                flow.interview_reference
                and interview_launch_url(flow.interview_reference)
            )
            if forms or interview:
                rendered.append(
                    _render_packet(forms, interview, court, topic, role)
                )
        elif name == "calendar" and deadlines:
            rendered.append(
                _render_calendar(deadlines, answers, court, topic, role)
            )
        elif name == "contacts" and contacts:
            rendered.append(_render_contacts(contacts, court, topic, role))
        elif name == "resources" and resources:
            rendered.append(_render_resources(resources))
        # else: a block with no rows, or a name the schema would have
        # rejected; leave it out
    if errors:
        _apply_errors(rendered, errors)
    return rendered


def _apply_errors(rendered, errors):
    """Put each inline error on its question and focus the first one, so
    keyboard and screen-reader users land on the error instead of hunting
    for it (WCAG 2.4.3 / 3.3.1)."""
    focused = False
    for section in rendered:
        for question in section.context.get("questions", ()):
            question["errors"] = errors.get(question["id"], [])
            if question["errors"] and not focused:
                question["autofocus"] = True
                focused = True


def _render_page(number, page, variables, answers, gates, cleared):
    return RenderedSection(
        anchor_id=f"interview-{number}",
        heading=page.title,
        template=f"{_TEMPLATE_DIR}/flow_section_fact_gather.html",
        context={
            "description": page.description,
            "questions": page_questions(variables, answers, gates, cleared),
        },
    )


def _render_info(anchor, section):
    return RenderedSection(
        anchor_id=anchor,
        heading=section.heading,
        template=f"{_TEMPLATE_DIR}/flow_section_info.html",
        context={"body": section.content},
    )


def _render_packet(forms, interview_available, court, topic, role):
    # URL parts, not a built URL: the template owns {% url %}.
    return RenderedSection(
        anchor_id="packet",
        heading=BLOCK_HEADINGS["packet"],
        template=f"{_TEMPLATE_DIR}/flow_section_packet.html",
        context={
            "forms": forms,
            "interview_available": interview_available,
            "court": court,
            "topic": topic,
            "role": role,
        },
    )


def _render_contacts(contacts, court, topic, role):
    # The template owns {% url %}, and the download id is the block name.
    return RenderedSection(
        anchor_id="contacts",
        heading=BLOCK_HEADINGS["contacts"],
        template=f"{_TEMPLATE_DIR}/flow_section_vcf.html",
        context={
            "contacts": contact_dicts(contacts, id_attr="ref"),
            "court": court,
            "topic": topic,
            "role": role,
            "output_id": "contacts",
        },
    )


def _render_resources(resources):
    return RenderedSection(
        anchor_id="resources",
        heading=BLOCK_HEADINGS["resources"],
        template=f"{_TEMPLATE_DIR}/flow_section_resources.html",
        context={"resources": resource_dicts(resources, id_attr="ref")},
    )


def _render_calendar(deadlines, answers, court, topic, role):
    # has_dates gates the download link, since an empty calendar is no use.
    resolved = [
        deadline_display(d) for d in flow_deadlines(deadlines, answers)
    ]
    return RenderedSection(
        anchor_id="calendar",
        heading=BLOCK_HEADINGS["calendar"],
        template=f"{_TEMPLATE_DIR}/flow_section_ics.html",
        context={
            "deadlines": resolved,
            "has_dates": any(d["date_iso"] for d in resolved),
            "court": court,
            "topic": topic,
            "role": role,
            "output_id": "calendar",
        },
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
        if "." not in value:
            return int(value)
        number = float(value)
        # A long enough decimal overflows to inf, which the JSON column
        # rejects, so it is an inline error rather than a 500.
        if not math.isfinite(number):
            raise ValueError(f"number overflows: {value[:20]!r}...")
        return number
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
