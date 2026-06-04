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

import pytest
from django.urls import resolve, reverse

from litigant_portal.app.topic_flow.renderer import RenderedSection
from litigant_portal.app.topic_flow.schema import (
    Corpus,
    FactGatherSection,
    InfoSection,
    Metadata,
    PacketOutput,
    Question,
    SummaryOutput,
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
