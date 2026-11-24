"""Tests for the c-molecules.save-status molecule, through the style guide
and the home page (Cotton tags compile only through django_cotton's
loader). Postgres-marked."""

import re

import pytest
from django.urls import reverse


@pytest.mark.postgres
@pytest.mark.django_db
def test_style_guide_renders_the_status_as_a_visible_live_region(
    client, settings
):
    settings.DEPLOYMENT_ENV = "dev"

    flat = re.sub(
        r"\s+", " ", client.get(reverse("pages:style_guide")).content.decode()
    )

    region = re.search(
        r'<div role="status" class="sr-only not-sr-only[^"]*"'
        r' x-data="saveStatus" data-text="Saved"[^>]*>(.*?)</div>',
        flat,
    )
    assert region
    assert "<svg" in region.group(1)
    assert re.search(
        r'<span x-text="text" class="sr-only sm:not-sr-only">Saved</span>',
        region.group(1),
    )


@pytest.mark.postgres
@pytest.mark.django_db
def test_the_header_holds_no_status_slot_without_a_message(client):
    html = client.get(reverse("pages:home")).content.decode()

    assert 'class="save-status"' not in html
    assert 'x-data="saveStatus"' not in html
