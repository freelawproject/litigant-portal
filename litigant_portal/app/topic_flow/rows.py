"""Build the guided page from TopicFlow rows.

The sibling of ``renderer.py`` for the ``TOPIC_FLOW_SOURCE=corpus`` path: it
reads the rows ``sync_corpus`` writes instead of the ``content/`` registry,
and produces the same ``RenderedSection`` list, so the page template does not
know which path built it. Pure: callers pass the prefetched rows in, and
nothing here touches the database or the request.

The flow's ``layout`` orders the page. A section key renders as an info
section anchored on that key, so chat citations can link to it. A block name
(``LAYOUT_BLOCKS``) renders as a placeholder until #1017 fills it in.
"""

from django.utils.translation import gettext_lazy as _

from litigant_portal.app.selectors.corpus import LAYOUT_BLOCKS
from litigant_portal.app.topic_flow.renderer import RenderedSection

_TEMPLATE_DIR = "cotton/molecules"

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


def render_flow(flow, sections, answers, errors=None) -> list[RenderedSection]:
    """One ``RenderedSection`` per layout entry, in layout order."""
    by_key = {section.key: section for section in sections}
    rendered = []
    for name in flow_layout(flow, sections):
        if name in by_key:
            rendered.append(_render_info(by_key[name]))
        else:
            rendered.append(_render_placeholder(name))
    return rendered


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
