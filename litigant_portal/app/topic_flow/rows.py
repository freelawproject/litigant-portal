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

from django.utils.translation import gettext_lazy as _

from litigant_portal.app.models.choices import VariableDataType
from litigant_portal.app.selectors.corpus import LAYOUT_BLOCKS
from litigant_portal.app.topic_flow.renderer import (
    NEVER_PREFILL,
    RenderedSection,
)

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


def flow_layout(flow, sections) -> list[str]:
    """The stored layout, or every section key then the blocks when empty."""
    return list(flow.layout) or [
        *(section.key for section in sections),
        *LAYOUT_BLOCKS,
    ]


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


def is_asked(variable, answers) -> bool:
    """Whether a variable's question currently applies."""
    if variable.asked_when is None:
        return True
    return answers.get(variable.asked_when.name) == variable.asked_when_value


def asked_names(pages, answers) -> list[str]:
    """Every variable currently asked, across all pages in order. The POST
    keys the entry view accepts."""
    return [
        variable.name
        for _page, variables in pages
        for variable in variables
        if is_asked(variable, answers)
    ]


def _form_value(value) -> str:
    """A stored (typed) answer as the string the form field shows."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def page_questions(variables, answers) -> list[dict]:
    """One question dict per asked variable, in placement order, in the shape
    the fact-gather template reads."""
    questions = []
    for variable in variables:
        if not is_asked(variable, answers):
            continue
        name = variable.name
        protected = name in NEVER_PREFILL
        stored = answers.get(name, variable.default)
        questions.append(
            {
                "id": name,
                "label": variable.label or name,
                "type": _QUESTION_TYPES[variable.data_type],
                "required": variable.required,
                "choices": (
                    BOOLEAN_CHOICES
                    if variable.data_type == VariableDataType.BOOLEAN
                    else variable.choices
                ),
                "help_text": variable.help_text,
                # Same leak guard as the content renderer: a protected field
                # renders blank and gets the clear checkbox instead (#638).
                "value": "" if protected else _form_value(stored),
                "saved": protected and name in answers,
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
    by_key = {section.key: section for section in sections}
    rendered = []
    for name in flow_layout(flow, sections):
        if name in by_key:
            rendered.append(_render_info(by_key[name]))
        elif name == "interview":
            rendered.extend(
                _render_page(number, page, variables, answers)
                for number, (page, variables) in enumerate(pages, 1)
            )
        else:
            rendered.append(_render_placeholder(name))
    return rendered


def _render_page(number, page, variables, answers):
    return RenderedSection(
        anchor_id=f"interview-{number}",
        heading=page.title,
        template=f"{_TEMPLATE_DIR}/flow_section_fact_gather.html",
        context={
            "description": page.description,
            "questions": page_questions(variables, answers),
        },
    )


def _render_info(section):
    return RenderedSection(
        anchor_id=section.key,
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
