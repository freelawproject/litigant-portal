"""Tests for the c-atoms.live-region atom, through the style guide (Cotton
tags compile only through django_cotton's loader). Postgres-marked."""

import re

import pytest
from django.urls import reverse


def _live_region_classes(content, role="status"):
    pattern = rf'<div(?=[^>]*\brole="{role}")[^>]*\bclass="([^"]*)"[^>]*>'
    return re.findall(pattern, content)


@pytest.mark.postgres
@pytest.mark.django_db
def test_style_guide_renders_a_hidden_and_a_visible_live_region(
    client, settings
):
    settings.DEPLOYMENT_ENV = "dev"

    response = client.get(reverse("pages:style_guide"))

    assert response.status_code == 200
    classes = [
        c.split() for c in _live_region_classes(response.content.decode())
    ]
    hidden = [c for c in classes if "not-sr-only" not in c]
    visible = [c for c in classes if "not-sr-only" in c]
    assert len(hidden) == 1 and "sr-only" in hidden[0]
    assert visible
