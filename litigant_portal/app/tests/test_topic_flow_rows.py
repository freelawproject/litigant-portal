"""Tests for ``topic_flow/rows.py``: the guided page built from TopicFlow
rows (#1016).

Every test here is DB-free and runs in the fast suite: rows are unsaved
model instances built in memory. The view tests that drive these through
the page live in ``test_topic_flow_rows_view.py``.
"""

from litigant_portal.app.models import TopicFlow, TopicFlowSection
from litigant_portal.app.selectors.corpus import LAYOUT_BLOCKS
from litigant_portal.app.topic_flow import rows
from litigant_portal.app.topic_flow.renderer import RenderedSection


def _section(key, heading="Heading", content="Body."):
    return TopicFlowSection(key=key, heading=heading, content=content)


SECTIONS = [
    _section("overview", "Overview", "Read this first."),
    _section("fees", "Fees", "Pay the fee."),
]


# --- layout -----------------------------------------------------------------


def test_layout_falls_back_to_sections_then_blocks_when_empty():
    flow = TopicFlow(layout=[])
    assert rows.flow_layout(flow, SECTIONS) == [
        "overview",
        "fees",
        *LAYOUT_BLOCKS,
    ]


def test_layout_is_used_as_stored_when_present():
    layout = ["packet", "fees", "interview", "overview"]
    flow = TopicFlow(layout=layout)
    assert rows.flow_layout(flow, SECTIONS) == layout


# --- render_flow ------------------------------------------------------------


def test_render_flow_gives_one_info_section_per_key_in_layout_order():
    flow = TopicFlow(layout=["fees", "overview"])
    rendered = rows.render_flow(flow, SECTIONS, {})
    assert all(isinstance(r, RenderedSection) for r in rendered)
    assert [r.anchor_id for r in rendered] == ["fees", "overview"]
    assert [r.heading for r in rendered] == ["Fees", "Overview"]
    assert [r.context["body"] for r in rendered] == [
        "Pay the fee.",
        "Read this first.",
    ]
    assert rendered[0].template == "cotton/molecules/flow_section_info.html"


def test_render_flow_gives_a_placeholder_per_block():
    flow = TopicFlow(layout=["overview", *LAYOUT_BLOCKS])
    rendered = rows.render_flow(flow, SECTIONS[:1], {})
    blocks = rendered[1:]
    assert [r.anchor_id for r in blocks] == list(LAYOUT_BLOCKS)
    assert [r.heading for r in blocks] == [
        rows.BLOCK_HEADINGS[name] for name in LAYOUT_BLOCKS
    ]
    assert all(
        r.template == "cotton/molecules/flow_section_placeholder.html"
        for r in blocks
    )
