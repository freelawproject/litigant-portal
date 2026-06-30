"""Topic Flow entry-view tests — 3-segment URL → rendered corpus sections.

The view resolves a corpus via the registry, renders every section through
``render_section`` (SectionRenderer, #479), and hands an ordered
``rendered_sections`` list to ``pages/topic_flow.html``. Item 4 is the strict
split: the page emits a heading + anchor per section (TOC works, JS off);
per-kind section *bodies* land with the section templates (Item 8).

URL-resolution tests are DB-free (they run in the fast suite). The render/404
tests drive the test client through template rendering, which touches the
auth/session machinery, so they need a database — run via Docker ``make test``.
"""

import re

import pytest
from django.urls import resolve, reverse

from litigant_portal.app.topic_flow.renderer import RenderedSection
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
    Resource,
    ResourcesOutput,
    SummaryOutput,
    VcfOutput,
)
from litigant_portal.app.views import pages

COURT, TOPIC, ROLE = "test-court", "test_topic", "petitioner"
URL = f"/t/{COURT}/{TOPIC}/{ROLE}/"
# Section ids, in corpus order — these become the rendered anchor_ids/TOC targets.
SECTION_IDS = ["overview", "key_dates", "filing_packet", "recap"]


def _corpus():
    """An in-memory corpus of only the four *registered* section kinds.

    The on-disk fixture also carries ics/vcf outputs, but those handlers aren't
    registered yet (Items 7/9) and render_section raises on them — so the view
    is exercised against a corpus it can fully render today.
    """
    return Corpus(
        metadata=Metadata(
            court=COURT, topic=TOPIC, role=ROLE, title="Test Flow"
        ),
        sections=[
            InfoSection(
                kind="info",
                id="overview",
                heading="What this covers",
                body="Read this first.",
            ),
            FactGatherSection(
                kind="fact_gather",
                id="key_dates",
                heading="Your dates",
                questions=[
                    Question(
                        id="publication_date",
                        label="Date your notice was published",
                        type="date",
                        required=True,
                    ),
                    Question(
                        id="filing_county",
                        label="County where you'll file",
                        type="choice",
                        choices=["Cass", "Burleigh"],
                    ),
                ],
            ),
            PacketOutput(
                kind="output",
                output_type="packet",
                id="filing_packet",
                heading="Your filing packet",
                forms=["Petition for Name Change"],
            ),
            SummaryOutput(
                kind="output",
                output_type="summary",
                id="recap",
                heading="Summary of what you entered",
            ),
        ],
    )


# --- URL resolution (DB-free) -----------------------------------------------


def test_three_segment_url_resolves_to_topic_flow_view():
    assert resolve(URL).view_name == "pages:topic_flow"


def test_two_segment_url_still_resolves_to_legacy_deep_link():
    # The 3-seg flow URL must not shadow the legacy 2-seg deep_link. `slug`
    # never crosses a `/`, so they're distinct — assert it, don't assume it.
    assert resolve(f"/t/{COURT}/{TOPIC}/").view_name == "pages:deep_link"


def test_topic_flow_url_reverses_with_three_segments():
    assert (
        reverse(
            "pages:topic_flow",
            kwargs={"court": COURT, "topic": TOPIC, "role": ROLE},
        )
        == URL
    )


# --- GET render (needs DB) --------------------------------------------------


@pytest.mark.django_db
def test_get_renders_topic_flow_page(client, monkeypatch):
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    response = client.get(URL)
    assert response.status_code == 200
    assert "pages/topic_flow.html" in [t.name for t in response.templates]


@pytest.mark.django_db
def test_context_carries_rendered_sections_in_corpus_order(
    client, monkeypatch
):
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    rendered = client.get(URL).context["rendered_sections"]
    # One RenderedSection per corpus section, same order — the view's core job.
    assert all(isinstance(r, RenderedSection) for r in rendered)
    assert [r.anchor_id for r in rendered] == SECTION_IDS


@pytest.mark.django_db
def test_page_emits_an_anchor_target_per_section(client, monkeypatch):
    # The TOC jumps to #anchor_id; assert the loop emits each target so anchor
    # navigation works with JS off. (Functional ids, not cosmetic markup.)
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    html = client.get(URL).content.decode()
    for section_id in SECTION_IDS:
        assert f'id="{section_id}"' in html


@pytest.mark.django_db
def test_unknown_flow_returns_404(client, monkeypatch):
    monkeypatch.setattr(pages.registry, "get", lambda *a: None)
    assert client.get(URL).status_code == 404


# --- Section body rendering (Item 8, needs DB) ------------------------------
# #483 emitted only the heading + anchor shell. These assert the per-kind body
# templates now render through `{% include section.template with ctx=... %}` —
# the functional payload (corpus content, form field names), not cosmetic markup.


@pytest.mark.django_db
def test_info_section_renders_its_body(client, monkeypatch):
    # Proves the include wiring resolves and the info partial gets its context —
    # the body the corpus supplied reaches the page, not just the heading.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    html = client.get(URL).content.decode()
    assert "Read this first." in html


@pytest.mark.django_db
def test_fact_gather_renders_post_form_with_a_field_per_question(
    client, monkeypatch
):
    # The form must POST and carry a `name` per question — the contract the
    # Item 5 POST handler reads. Without these names, answers can't persist.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    html = client.get(URL).content.decode()
    assert 'method="post"' in html
    assert "csrfmiddlewaretoken" in html
    assert 'name="publication_date"' in html
    assert 'name="filing_county"' in html


@pytest.mark.django_db
def test_fact_gather_choice_question_renders_its_options(client, monkeypatch):
    # A choice question must render its options, else the user can't answer it.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    html = client.get(URL).content.decode()
    assert "<option" in html
    assert "Cass" in html
    assert "Burleigh" in html


@pytest.mark.django_db
def test_packet_section_lists_each_form(client, monkeypatch):
    # The packet partial must render every form name the corpus declares.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    html = client.get(URL).content.decode()
    assert "Petition for Name Change" in html


@pytest.mark.django_db
def test_packet_form_with_url_renders_as_link(client, monkeypatch):
    # A form that carries a url renders its name as a link to the official PDF
    # (#495); a name-only form stays plain text. Functional target, not markup.
    pdf = "https://www.ndcourts.gov/petition.pdf"
    corpus = Corpus(
        metadata=Metadata(court=COURT, topic=TOPIC, role=ROLE, title="T"),
        sections=[
            PacketOutput(
                kind="output",
                output_type="packet",
                id="filing_packet",
                heading="Your filing packet",
                forms=[
                    {"name": "Petition for Name Change", "url": pdf},
                    "Confidential Information Form",
                ],
            ),
        ],
    )
    monkeypatch.setattr(pages.registry, "get", lambda *a: corpus)
    flat = re.sub(r"\s+", " ", client.get(URL).content.decode())
    # Linked form → anchor to its PDF; name-only form → present, unlinked.
    assert re.search(
        rf'<a[^>]*href="{re.escape(pdf)}"[^>]*>[^<]*Petition for Name Change',
        flat,
    )
    assert "Confidential Information Form" in flat


@pytest.mark.django_db
def test_resources_section_renders_links(client, monkeypatch):
    # A resources output renders each official link as an anchor to its url
    # (#519) — the cleanup that retires plain-text URLs in info bodies.
    # Functional target (the link is clickable), not markup.
    url = "https://www.ndcourts.gov/legal-self-help/name-change-adult"
    corpus = Corpus(
        metadata=Metadata(court=COURT, topic=TOPIC, role=ROLE, title="T"),
        resources=[
            Resource(id="guidance", label="Name-change guidance", url=url),
        ],
        sections=[
            ResourcesOutput(
                kind="output",
                output_type="resources",
                id="official_resources",
                heading="Official resources",
                resource_ids=["guidance"],
            ),
        ],
    )
    monkeypatch.setattr(pages.registry, "get", lambda *a: corpus)
    flat = re.sub(r"\s+", " ", client.get(URL).content.decode())
    assert re.search(
        rf'<a[^>]*href="{re.escape(url)}"[^>]*>[^<]*Name-change guidance',
        flat,
    )


def _field_tag(html, name):
    """The <input>/<select> element whose name == ``name``, whitespace flattened.

    The atoms render one attribute per line, so flatten before matching so a
    multi-line tag reads as one string.
    """
    flat = re.sub(r"\s+", " ", html)
    match = re.search(
        rf'<(?:input|select)\b[^>]*name="{re.escape(name)}"[^>]*>', flat
    )
    return match.group(0) if match else ""


@pytest.mark.django_db
def test_fact_gather_marks_required_questions_and_leaves_optional_unmarked(
    client, monkeypatch
):
    # The HTML `required` attribute must track the corpus `required` flag:
    # publication_date is required=True, filing_county defaults required=False.
    # If an optional field renders required, the browser blocks the litigant on
    # a question the author meant to be skippable — the bug this guards.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    html = client.get(URL).content.decode()
    assert re.search(r"\brequired\b", _field_tag(html, "publication_date"))
    assert not re.search(r"\brequired\b", _field_tag(html, "filing_county"))


@pytest.mark.django_db
def test_headingless_fact_gather_skipped_in_toc_but_body_still_renders(
    client, monkeypatch
):
    # fact_gather is the one section whose heading is optional. A headingless
    # one must not emit an empty (nameless) TOC link — guard the TOC entry, not
    # the anchor/section, so its body still renders.
    corpus = Corpus(
        metadata=Metadata(court=COURT, topic=TOPIC, role=ROLE, title="T"),
        sections=[
            InfoSection(
                kind="info",
                id="overview",
                heading="What this covers",
                body="Read this first.",
            ),
            FactGatherSection(
                kind="fact_gather",
                id="key_dates",
                questions=[
                    Question(id="publication_date", label="When", type="date")
                ],
            ),
        ],
    )
    monkeypatch.setattr(pages.registry, "get", lambda *a: corpus)
    html = client.get(URL).content.decode()
    assert 'href="#overview"' in html  # heading section -> TOC link
    assert 'href="#key_dates"' not in html  # headingless -> no empty link
    assert 'name="publication_date"' in html  # body still renders


# --- fact_gather POST + prefill (Item 5, needs DB) --------------------------
# The form rendered by #486 now persists. POST writes answers to the
# session-backed AnswerStore and redirects (PRG); the redirected GET prefills
# the form. Functional contract — answers survive a reload — not markup.


@pytest.mark.django_db
def test_post_persists_answers_and_redirects_prg(client, monkeypatch):
    # Post-Redirect-Get: the POST must 302 back to the flow URL, never render
    # 200 in place. Otherwise a browser reload re-submits the form.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    response = client.post(
        URL, {"publication_date": "2026-02-01", "filing_county": "Cass"}
    )
    assert response.status_code == 302
    assert response["Location"].startswith(URL)


@pytest.mark.django_db
def test_post_redirects_to_the_saved_section_anchor(client, monkeypatch):
    # Scroll restore (#510): the PRG lands on the fact_gather section's anchor,
    # so saving returns the litigant to the form they were filling — and the
    # deadlines that recompute just below it — not the top of the page.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    response = client.post(
        URL, {"publication_date": "2026-02-01", "filing_county": "Cass"}
    )
    assert response["Location"] == f"{URL}#key_dates"


@pytest.mark.django_db
def test_posted_answers_prefill_on_the_redirected_get(client, monkeypatch):
    # The whole point: what you submitted comes back filled in. Text echoes its
    # value; the choice marks its option selected.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    client.post(
        URL, {"publication_date": "2026-02-01", "filing_county": "Cass"}
    )
    html = client.get(URL).content.decode()
    flat = re.sub(r"\s+", " ", html)
    assert 'value="2026-02-01"' in _field_tag(html, "publication_date")
    assert re.search(r'<option value="Cass"[^>]*selected', flat)


@pytest.mark.django_db
def test_get_prefills_form_from_existing_session_answers(client, monkeypatch):
    # Answers already in the session (e.g. a returning guest) prefill on a plain
    # GET — the AnswerStore is the source, not just the immediately-prior POST.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    session = client.session
    session["topic_flow"] = {
        f"{COURT}/{TOPIC}/{ROLE}": {"publication_date": "2026-03-15"}
    }
    session.save()
    html = client.get(URL).content.decode()
    assert 'value="2026-03-15"' in _field_tag(html, "publication_date")


@pytest.mark.django_db
def test_post_stores_only_known_question_ids(client, monkeypatch):
    # The handler accepts only the corpus's question ids — csrf tokens and any
    # stray/injected POST keys must not land in the answer store.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    client.post(URL, {"publication_date": "2026-02-01", "not_a_question": "x"})
    flow = client.session["topic_flow"][f"{COURT}/{TOPIC}/{ROLE}"]
    assert flow.get("publication_date") == "2026-02-01"
    assert "not_a_question" not in flow


# --- fact_gather POST validation (#525, needs DB) ---------------------------
# The handler now validates against the corpus question defs before persisting:
# empty `required` fields and `choice` answers outside the list are soft-gated
# with inline errors (re-render, not PRG) and never stored. JS-off-safe.


def _flow_answers(client):
    return client.session.get("topic_flow", {}).get(
        f"{COURT}/{TOPIC}/{ROLE}", {}
    )


@pytest.mark.django_db
def test_post_empty_required_rerenders_in_place(client, monkeypatch):
    # Invalid submit soft-gates: re-render 200 (so the inline error shows),
    # not a PRG 302. A 302 would bounce the litigant forward past the gap.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    response = client.post(URL, {"publication_date": "", "filing_county": ""})
    assert response.status_code == 200


@pytest.mark.django_db
def test_post_empty_required_is_not_persisted(client, monkeypatch):
    # The blank required answer must not land in the store — otherwise the
    # litigant could advance toward filing with a missing answer.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    client.post(URL, {"publication_date": "", "filing_county": ""})
    assert "publication_date" not in _flow_answers(client)


@pytest.mark.django_db
def test_post_empty_required_marks_the_field_invalid(client, monkeypatch):
    # The offending field carries aria-invalid="true" — the JS-off-safe a11y
    # signal the form-field error pattern renders. Functional, not copy.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    html = client.post(
        URL, {"publication_date": "", "filing_county": ""}
    ).content.decode()
    flat = re.sub(r"\s+", " ", html)
    assert re.search(r'name="publication_date"[^>]*aria-invalid="true"', flat)


@pytest.mark.django_db
def test_post_choice_outside_list_is_rejected_not_stored(client, monkeypatch):
    # A choice answer outside the declared options is dropped, never persisted
    # (the silent-accept hole this issue closes).
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    response = client.post(
        URL, {"publication_date": "2026-02-01", "filing_county": "Stark"}
    )
    assert response.status_code == 200
    assert "filing_county" not in _flow_answers(client)


@pytest.mark.django_db
def test_post_saves_valid_fields_even_when_a_sibling_is_invalid(
    client, monkeypatch
):
    # Partial-invalid submit: the valid field still persists so the litigant
    # doesn't lose good input on every fix-and-resubmit; only the bad one is
    # flagged. (publication_date valid, filing_county out-of-list.)
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    client.post(
        URL, {"publication_date": "2026-02-01", "filing_county": "Stark"}
    )
    answers = _flow_answers(client)
    assert answers.get("publication_date") == "2026-02-01"
    assert "filing_county" not in answers


@pytest.mark.django_db
def test_post_all_valid_still_redirects_prg(client, monkeypatch):
    # The happy path is unchanged: a fully valid submit persists and 302s (PRG).
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    response = client.post(
        URL, {"publication_date": "2026-02-01", "filing_county": "Cass"}
    )
    assert response.status_code == 302
    assert _flow_answers(client).get("filing_county") == "Cass"


@pytest.mark.django_db
def test_error_rerender_does_not_leak_rejected_value(client, monkeypatch):
    # The soft-gate re-renders from the stored answers, not the raw submission,
    # so a rejected choice ("Stark") appears nowhere — the fact_gather form
    # flags it, but the summary section can't echo it as a saved answer. Guards
    # against the page contradicting itself (form says "fix", summary says "ok").
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    html = client.post(
        URL, {"publication_date": "2026-02-01", "filing_county": "Stark"}
    ).content.decode()
    assert "Stark" not in html


@pytest.mark.django_db
def test_post_persists_stripped_value(client, monkeypatch):
    # validate_answers checks the stripped value, so storage must strip too —
    # else a padded choice validates but fails the strict option-selected match
    # on re-render, and a padded date breaks date.fromisoformat downstream.
    monkeypatch.setattr(pages.registry, "get", lambda *a: _corpus())
    client.post(
        URL, {"publication_date": "2026-02-01", "filing_county": "Cass  "}
    )
    assert _flow_answers(client).get("filing_county") == "Cass"


# --- ics deadline rendering (#494, needs DB) --------------------------------
# The ics output renders a personalized deadline computed from the stored
# answer — fact_gather → AnswerStore → compute_deadline → on-page date, JS off.


def _corpus_with_deadline():
    return Corpus(
        metadata=Metadata(court=COURT, topic=TOPIC, role=ROLE, title="T"),
        deadlines=[
            Deadline(
                id="publication_wait",
                label="30-day publication wait",
                offset_days=30,
                offset_from="publication_date",
            )
        ],
        sections=[
            FactGatherSection(
                kind="fact_gather",
                id="key_dates",
                heading="Your dates",
                questions=[
                    Question(
                        id="publication_date",
                        label="Date your notice was published",
                        type="date",
                        required=True,
                    )
                ],
            ),
            IcsOutput(
                kind="output",
                output_type="ics",
                id="deadlines_calendar",
                heading="Add deadlines to your calendar",
                deadline_ids=["publication_wait"],
            ),
        ],
    )


@pytest.mark.django_db
def test_ics_section_renders_personalized_deadline(client, monkeypatch):
    # The payoff: a stored answer drives compute_deadline and the concrete date
    # appears on the page, server-rendered. 30 days after 2026-02-01 = 2026-03-03.
    monkeypatch.setattr(
        pages.registry, "get", lambda *a: _corpus_with_deadline()
    )
    session = client.session
    session["topic_flow"] = {
        f"{COURT}/{TOPIC}/{ROLE}": {"publication_date": "2026-02-01"}
    }
    session.save()
    html = client.get(URL).content.decode()
    assert 'datetime="2026-03-03"' in html  # machine-readable <time>
    assert "March 3, 2026" in html  # human-readable date


@pytest.mark.django_db
def test_ics_section_pending_without_answer_still_renders(client, monkeypatch):
    # Graceful missing-answer state: page still renders, deadline label shows,
    # but no computed date is emitted (nothing to compute yet).
    monkeypatch.setattr(
        pages.registry, "get", lambda *a: _corpus_with_deadline()
    )
    html = client.get(URL).content.decode()
    assert "30-day publication wait" in html
    assert "March 3, 2026" not in html
    assert 'datetime="2026-03-03"' not in html


# --- ics download (#504, needs DB) ------------------------------------------
# The output-download route: GET .../download/<output_id>/ streams the section
# as a file, dispatching on output_type. The .ics is built from the same stored
# answers the page renders, so the calendar matches what's on screen.

DOWNLOAD_URL = f"/t/{COURT}/{TOPIC}/{ROLE}/download/deadlines_calendar/"


def test_download_url_resolves_to_the_download_view():
    assert resolve(DOWNLOAD_URL).view_name == "pages:topic_flow_download"


def test_download_url_reverses_with_the_output_id():
    assert (
        reverse(
            "pages:topic_flow_download",
            kwargs={
                "court": COURT,
                "topic": TOPIC,
                "role": ROLE,
                "output_id": "deadlines_calendar",
            },
        )
        == DOWNLOAD_URL
    )


@pytest.mark.django_db
def test_download_streams_ics_attachment_with_the_computed_deadline(
    client, monkeypatch
):
    # The payoff: the stored answer drives the same compute_deadline path, and
    # the downloaded calendar carries the concrete date as an all-day event.
    monkeypatch.setattr(
        pages.registry, "get", lambda *a: _corpus_with_deadline()
    )
    session = client.session
    session["topic_flow"] = {
        f"{COURT}/{TOPIC}/{ROLE}": {"publication_date": "2026-02-01"}
    }
    session.save()
    response = client.get(DOWNLOAD_URL)
    assert response.status_code == 200
    assert "text/calendar" in response["Content-Type"]
    assert (
        'attachment; filename="deadlines_calendar.ics"'
        in response["Content-Disposition"]
    )
    body = response.content.decode()
    assert "BEGIN:VCALENDAR" in body
    assert "20260303" in body  # all-day DATE form of 2026-03-03


@pytest.mark.django_db
def test_download_without_answers_is_an_empty_but_valid_calendar(
    client, monkeypatch
):
    # No stored answer → 200 with a valid, event-free calendar (not a 500/404).
    monkeypatch.setattr(
        pages.registry, "get", lambda *a: _corpus_with_deadline()
    )
    response = client.get(DOWNLOAD_URL)
    assert response.status_code == 200
    body = response.content.decode()
    assert "BEGIN:VCALENDAR" in body
    assert "BEGIN:VEVENT" not in body


@pytest.mark.django_db
def test_download_unknown_flow_returns_404(client, monkeypatch):
    monkeypatch.setattr(pages.registry, "get", lambda *a: None)
    assert client.get(DOWNLOAD_URL).status_code == 404


@pytest.mark.django_db
def test_download_non_downloadable_output_returns_404(client, monkeypatch):
    # key_dates is a fact_gather, not a downloadable output — gated to 404.
    monkeypatch.setattr(
        pages.registry, "get", lambda *a: _corpus_with_deadline()
    )
    url = f"/t/{COURT}/{TOPIC}/{ROLE}/download/key_dates/"
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_ics_section_links_to_the_download_once_a_date_is_entered(
    client, monkeypatch
):
    # The page must surface a reachable link to the download URL — without it
    # the litigant can't get the calendar file. Functional target, not markup.
    monkeypatch.setattr(
        pages.registry, "get", lambda *a: _corpus_with_deadline()
    )
    session = client.session
    session["topic_flow"] = {
        f"{COURT}/{TOPIC}/{ROLE}": {"publication_date": "2026-02-01"}
    }
    session.save()
    html = client.get(URL).content.decode()
    assert f'href="{DOWNLOAD_URL}"' in html


@pytest.mark.django_db
def test_ics_section_hides_download_link_until_a_date_is_entered(
    client, monkeypatch
):
    # No computable date → no link (an empty calendar is no use). Guards the
    # has_dates gate end-to-end, the mirror of the link-present case above.
    monkeypatch.setattr(
        pages.registry, "get", lambda *a: _corpus_with_deadline()
    )
    html = client.get(URL).content.decode()
    assert f'href="{DOWNLOAD_URL}"' not in html


# --- vcf download (#473, needs DB) ------------------------------------------
# The same generic download route, dispatching on output_type to the vCard
# builder. Contacts are static corpus data, so the .vcf needs no stored answers
# — it downloads the same card set the page shows.

VCF_DOWNLOAD_URL = f"/t/{COURT}/{TOPIC}/{ROLE}/download/contacts_card/"


def _corpus_with_contact():
    return Corpus(
        metadata=Metadata(court=COURT, topic=TOPIC, role=ROLE, title="T"),
        contacts=[
            Contact(id="clerk", name="Clerk of Court", phone="555-1234")
        ],
        sections=[
            VcfOutput(
                kind="output",
                output_type="vcf",
                id="contacts_card",
                heading="Save these contacts",
                contact_ids=["clerk"],
            ),
        ],
    )


@pytest.mark.django_db
def test_vcf_download_streams_vcard_attachment_with_the_contact(
    client, monkeypatch
):
    # The payoff: the generic route dispatches a vcf section to the vCard
    # builder and streams it as a .vcf attachment carrying the contact.
    monkeypatch.setattr(
        pages.registry, "get", lambda *a: _corpus_with_contact()
    )
    response = client.get(VCF_DOWNLOAD_URL)
    assert response.status_code == 200
    assert "text/vcard" in response["Content-Type"]
    assert (
        'attachment; filename="contacts_card.vcf"'
        in response["Content-Disposition"]
    )
    body = response.content.decode()
    assert "BEGIN:VCARD" in body
    assert "Clerk of Court" in body


@pytest.mark.django_db
def test_vcf_section_links_to_the_download(client, monkeypatch):
    # The page must surface a reachable link to the .vcf — without it the
    # litigant can't save the contacts. Functional target, not markup. No
    # gate (unlike ics): contacts are always present, so the link always shows.
    monkeypatch.setattr(
        pages.registry, "get", lambda *a: _corpus_with_contact()
    )
    html = client.get(URL).content.decode()
    assert f'href="{VCF_DOWNLOAD_URL}"' in html
