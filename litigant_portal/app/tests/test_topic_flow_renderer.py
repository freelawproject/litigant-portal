"""SectionRenderer tests — registry dispatch of corpus sections to render context.

The renderer is a fat, pure function of ``(section, corpus, answers)`` → a
``RenderedSection`` carrying a template path + flat, dumb context. It takes a
plain ``answers`` dict (not an AnswerStore), so these tests need no session or
DB. The ``ics`` handler renders its deadline list here (#494); ``vcf`` is still
intentionally unregistered — it lands with its download-view item (#441) — so
rendering one fails fast.
"""

import pytest

from litigant_portal.app.topic_flow.renderer import (
    RenderedSection,
    render_section,
)
from litigant_portal.app.topic_flow.schema import (
    Corpus,
    Deadline,
    FactGatherSection,
    IcsOutput,
    InfoSection,
    Metadata,
    PacketOutput,
    Question,
    SummaryOutput,
    VcfOutput,
)


def _corpus(*sections, deadlines=None):
    return Corpus(
        metadata=Metadata(court="c", topic="t", role="r", title="T"),
        deadlines=deadlines or [],
        sections=list(sections),
    )


# --- info -------------------------------------------------------------------


def test_info_renders_heading_and_body():
    section = InfoSection(
        kind="info", id="intro", heading="Your rights", body="Read this."
    )
    rendered = render_section(section, _corpus(section), {})
    assert isinstance(rendered, RenderedSection)
    assert rendered.anchor_id == "intro"
    assert rendered.heading == "Your rights"
    assert rendered.context["body"] == "Read this."


# --- fact_gather ------------------------------------------------------------


def _fg(questions, heading=None, id="facts"):
    return FactGatherSection(
        kind="fact_gather", id=id, heading=heading, questions=questions
    )


def test_fact_gather_prefills_answered_questions():
    section = _fg(
        [Question(id="pubdate", label="Publication date", type="date")]
    )
    rendered = render_section(
        section, _corpus(section), {"pubdate": "2026-05-01"}
    )
    (q,) = rendered.context["questions"]
    assert q["id"] == "pubdate"
    assert q["label"] == "Publication date"
    assert q["value"] == "2026-05-01"


def test_fact_gather_unanswered_question_prefills_empty():
    section = _fg(
        [Question(id="pubdate", label="Publication date", type="date")]
    )
    rendered = render_section(section, _corpus(section), {})
    (q,) = rendered.context["questions"]
    assert q["value"] == ""


def test_fact_gather_carries_choice_metadata():
    section = _fg(
        [
            Question(
                id="track",
                label="Track",
                type="choice",
                choices=["standard", "waiver"],
            )
        ]
    )
    rendered = render_section(section, _corpus(section), {})
    (q,) = rendered.context["questions"]
    assert q["type"] == "choice"
    assert q["choices"] == ["standard", "waiver"]


def test_fact_gather_heading_optional():
    section = _fg([Question(id="x", label="X")], heading=None)
    rendered = render_section(section, _corpus(section), {})
    assert rendered.heading == ""


# --- summary ----------------------------------------------------------------


def test_summary_pairs_answers_with_labels_in_corpus_order():
    fg = _fg(
        [
            Question(id="name", label="Full name"),
            Question(id="dob", label="Date of birth", type="date"),
        ]
    )
    summary = SummaryOutput(
        kind="output",
        output_type="summary",
        id="recap",
        heading="Your answers",
    )
    corpus = _corpus(fg, summary)
    # answers inserted out of corpus order — summary must follow corpus order.
    rendered = render_section(
        summary, corpus, {"dob": "1990-02-03", "name": "Sandra"}
    )
    assert rendered.context["items"] == [
        {"label": "Full name", "value": "Sandra"},
        {"label": "Date of birth", "value": "1990-02-03"},
    ]


def test_summary_omits_unanswered_questions():
    fg = _fg(
        [
            Question(id="name", label="Full name"),
            Question(id="dob", label="DOB"),
        ]
    )
    summary = SummaryOutput(
        kind="output", output_type="summary", id="recap", heading="Recap"
    )
    rendered = render_section(
        summary, _corpus(fg, summary), {"name": "Sandra"}
    )
    assert rendered.context["items"] == [
        {"label": "Full name", "value": "Sandra"}
    ]


# --- packet -----------------------------------------------------------------


def test_packet_renders_form_list():
    section = PacketOutput(
        kind="output",
        output_type="packet",
        id="forms",
        heading="Your packet",
        forms=["Petition for Name Change", "Order"],
    )
    rendered = render_section(section, _corpus(section), {})
    assert rendered.heading == "Your packet"
    assert rendered.context["forms"] == ["Petition for Name Change", "Order"]


# --- dispatch ---------------------------------------------------------------


def test_each_kind_dispatches_to_a_distinct_template():
    info = InfoSection(kind="info", id="i", heading="I", body="B")
    fg = _fg([Question(id="q", label="Q")])
    summ = SummaryOutput(
        kind="output", output_type="summary", id="s", heading="S"
    )
    packet = PacketOutput(
        kind="output", output_type="packet", id="p", heading="P", forms=["F"]
    )
    corpus = _corpus(info, fg, summ, packet)
    templates = {
        render_section(s, corpus, {}).template
        for s in (info, fg, summ, packet)
    }
    assert len(templates) == 4  # four kinds → four distinct templates
    assert all(t for t in templates)  # all non-empty


# --- ics (deadline rendering, #494) -----------------------------------------
# The ics output renders each referenced deadline computed from the user's
# answers (compute_deadline's first caller). The .ics download button lands
# with #441; this is the visible, JS-off date list.

_PUB_Q = Question(id="publication_date", label="Publication date", type="date")
_PUB_DEADLINE = Deadline(
    id="publication_wait",
    label="30-day publication wait",
    offset_days=30,
    offset_from="publication_date",
    description="The judge can review 30 days after publication.",
)


def _ics_corpus(
    deadline_ids=("publication_wait",), deadlines=(_PUB_DEADLINE,)
):
    ics = IcsOutput(
        kind="output",
        output_type="ics",
        id="cal",
        heading="Add deadlines to your calendar",
        deadline_ids=list(deadline_ids),
    )
    corpus = _corpus(_fg([_PUB_Q], id="dates"), ics, deadlines=list(deadlines))
    return corpus, ics


def test_ics_renders_computed_deadline_from_answer():
    corpus, ics = _ics_corpus()
    rendered = render_section(ics, corpus, {"publication_date": "2026-02-01"})
    (d,) = rendered.context["deadlines"]
    assert d["label"] == "30-day publication wait"
    # 30 days after 2026-02-01 = 2026-03-03 (Feb 2026 has 28 days).
    assert d["date_iso"] == "2026-03-03"
    assert "March 3, 2026" in d["date_display"]


def test_ics_deadline_pending_when_answer_missing():
    corpus, ics = _ics_corpus()
    rendered = render_section(ics, corpus, {})
    (d,) = rendered.context["deadlines"]
    assert d["date_iso"] is None
    assert d["date_display"] is None
    assert d["label"] == "30-day publication wait"  # label still shown


def test_ics_deadline_pending_when_answer_malformed():
    corpus, ics = _ics_corpus()
    rendered = render_section(ics, corpus, {"publication_date": "not-a-date"})
    (d,) = rendered.context["deadlines"]
    assert d["date_iso"] is None


def test_ics_carries_deadline_description():
    corpus, ics = _ics_corpus()
    rendered = render_section(ics, corpus, {})
    (d,) = rendered.context["deadlines"]
    assert (
        d["description"] == "The judge can review 30 days after publication."
    )


def test_ics_lists_deadlines_in_deadline_ids_order():
    # Order follows the section's deadline_ids, not corpus.deadlines order.
    second = Deadline(
        id="second",
        label="Second",
        offset_days=5,
        offset_from="publication_date",
    )
    corpus, ics = _ics_corpus(
        deadline_ids=("second", "publication_wait"),
        deadlines=(_PUB_DEADLINE, second),
    )
    rendered = render_section(ics, corpus, {"publication_date": "2026-02-01"})
    assert [d["label"] for d in rendered.context["deadlines"]] == [
        "Second",
        "30-day publication wait",
    ]


# --- fail-fast on unregistered (vcf lands with its download view, #441) ------


def test_unregistered_output_type_raises():
    vcf = VcfOutput(
        kind="output",
        output_type="vcf",
        id="contact",
        heading="Save the clerk's contact",
        contact_ids=["clerk"],
    )
    with pytest.raises(ValueError, match="vcf"):
        render_section(vcf, _corpus(vcf), {})
