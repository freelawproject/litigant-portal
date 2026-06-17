"""SectionRenderer tests — registry dispatch of corpus sections to render context.

The renderer is a fat, pure function of ``(section, corpus, answers)`` → a
``RenderedSection`` carrying a template path + flat, dumb context. It takes a
plain ``answers`` dict (not an AnswerStore), so these tests need no session or
DB. The ``ics`` handler renders its deadline list here (#494); the ``vcf``
handler renders its contact list (#473). An output_type with no registered
handler is a code gap and fails fast.
"""

from datetime import date
from types import SimpleNamespace

import pytest

from litigant_portal.app.topic_flow.renderer import (
    RenderedSection,
    _format_deadline_date,
    render_section,
    submitted_section_anchor,
)
from litigant_portal.app.topic_flow.schema import (
    Contact,
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


def _corpus(*sections, deadlines=None, contacts=None):
    return Corpus(
        metadata=Metadata(court="c", topic="t", role="r", title="T"),
        deadlines=deadlines or [],
        contacts=contacts or [],
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


def test_packet_without_interview_url_exposes_none():
    """No interview_url → context carries None, so the template shows no
    handoff button. Existing packet corpora are unaffected."""
    section = PacketOutput(
        kind="output",
        output_type="packet",
        id="forms",
        heading="Your packet",
        forms=["Petition for Name Change"],
    )
    rendered = render_section(section, _corpus(section), {})
    assert rendered.context["interview_url"] is None


def test_packet_with_interview_url_exposes_it_for_the_button():
    """interview_url reaches the template context verbatim — that's what drives
    the 'Fill out your forms' link-out (#543)."""
    url = "https://da.example/interview?i=docassemble.playground"
    section = PacketOutput(
        kind="output",
        output_type="packet",
        id="forms",
        heading="Your packet",
        forms=["Petition for Name Change"],
        interview_url=url,
    )
    rendered = render_section(section, _corpus(section), {})
    assert rendered.context["interview_url"] == url


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
# answers, via resolve_ics_deadlines (shared with the .ics download, #504).
# These cover the visible, JS-off date list + the download-link context.

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


def test_format_deadline_date_single_digit_day_has_no_leading_zero():
    # The display drops the leading zero on the day ("March 3", not "March 03")
    # and must do so without strftime's %-d — a glibc/BSD extension that raises
    # ValueError on platforms whose C library lacks it (Windows), which would
    # crash deadline rendering for a partner self-hosting there (#526). Pinning
    # the exact string guards both the no-leading-zero contract and a regression
    # back to %d.
    assert _format_deadline_date(date(2026, 3, 3)) == "Tuesday, March 3, 2026"


def test_format_deadline_date_double_digit_day():
    assert (
        _format_deadline_date(date(2026, 12, 25))
        == "Friday, December 25, 2026"
    )


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


def test_ics_has_dates_true_when_a_deadline_is_computed():
    # Gates the download link: a calendar with at least one dated event.
    corpus, ics = _ics_corpus()
    rendered = render_section(ics, corpus, {"publication_date": "2026-02-01"})
    assert rendered.context["has_dates"] is True


def test_ics_has_dates_false_when_nothing_is_computed():
    # No answer → no datable event → no download link shown.
    corpus, ics = _ics_corpus()
    rendered = render_section(ics, corpus, {})
    assert rendered.context["has_dates"] is False


def test_ics_context_carries_download_url_parts():
    # The template builds {% url 'pages:topic_flow_download' ... %} from these,
    # so the renderer stays Django-free (no reverse() call).
    corpus, ics = _ics_corpus()
    ctx = render_section(ics, corpus, {}).context
    assert ctx["output_id"] == ics.id
    assert (ctx["court"], ctx["topic"], ctx["role"]) == (
        corpus.metadata.court,
        corpus.metadata.topic,
        corpus.metadata.role,
    )


# --- fail-fast on unregistered (vcf lands with its download view, #441) ------


def test_unregistered_output_type_raises():
    # Every real output_type is now registered, so the fail-fast invariant is
    # tested with a stand-in carrying an output_type no handler knows. A new
    # union member shipped without a renderer must blow up, not render blank.
    bogus = SimpleNamespace(kind="output", output_type="zip", id="x")
    # corpus is irrelevant — dispatch raises on the unknown key before using it.
    with pytest.raises(ValueError, match="zip"):
        render_section(bogus, None, {})


# --- vcf (contact rendering, #473) ------------------------------------------
# The vcf output renders each referenced contact via resolve_vcf_contacts
# (shared with the .vcf download, #473). Contacts are static — no answers, no
# pending state — so the download link always shows.

_CLERK = Contact(
    id="clerk",
    name="Clerk of Court",
    phone="555-1234",
    note="Window 3",
)


def _vcf_corpus(contact_ids=("clerk",), contacts=(_CLERK,)):
    vcf = VcfOutput(
        kind="output",
        output_type="vcf",
        id="contacts",
        heading="Save these contacts",
        contact_ids=list(contact_ids),
    )
    corpus = _corpus(vcf, contacts=list(contacts))
    return corpus, vcf


def test_vcf_renders_referenced_contact():
    corpus, vcf = _vcf_corpus()
    (c,) = render_section(vcf, corpus, {}).context["contacts"]
    assert c["name"] == "Clerk of Court"
    assert c["phone"] == "555-1234"
    assert c["note"] == "Window 3"


def test_vcf_lists_contacts_in_contact_ids_order():
    aid = Contact(id="aid", name="Legal Aid")
    corpus, vcf = _vcf_corpus(
        contact_ids=("aid", "clerk"), contacts=(_CLERK, aid)
    )
    contacts = render_section(vcf, corpus, {}).context["contacts"]
    assert [c["name"] for c in contacts] == ["Legal Aid", "Clerk of Court"]


def test_vcf_context_carries_download_url_parts():
    # The template builds {% url 'pages:topic_flow_download' ... %} from these.
    corpus, vcf = _vcf_corpus()
    ctx = render_section(vcf, corpus, {}).context
    assert ctx["output_id"] == vcf.id
    assert (ctx["court"], ctx["topic"], ctx["role"]) == (
        corpus.metadata.court,
        corpus.metadata.topic,
        corpus.metadata.role,
    )


def test_vcf_uses_the_vcf_template():
    corpus, vcf = _vcf_corpus()
    rendered = render_section(vcf, corpus, {})
    assert rendered.template.endswith("flow_section_vcf.html")


# --- submitted_section_anchor (PRG scroll restore, #510) --------------------
# The entry view redirects a saved form back to its section anchor so the
# litigant keeps their place. The anchor is matched by submitted question-id
# overlap, so the right section wins even with multiple fact_gather forms.


def test_anchor_is_the_section_owning_the_submitted_ids():
    section = _fg([Question(id="pubdate", label="Date")], id="key_dates")
    assert (
        submitted_section_anchor(_corpus(section), {"pubdate"}) == "key_dates"
    )


def test_anchor_picks_the_form_that_was_submitted_not_just_the_first():
    dates = _fg([Question(id="pubdate", label="Date")], id="dates")
    contact = _fg([Question(id="phone", label="Phone")], id="contact_info")
    corpus = _corpus(dates, contact)
    # Only the second form's field was posted → its anchor, not "dates".
    assert submitted_section_anchor(corpus, {"phone"}) == "contact_info"


def test_anchor_is_none_when_nothing_overlaps():
    section = _fg([Question(id="pubdate", label="Date")], id="key_dates")
    assert submitted_section_anchor(_corpus(section), {"unknown"}) is None
    assert submitted_section_anchor(_corpus(section), set()) is None
