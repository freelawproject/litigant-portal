"""topic_court_find: the court the site is on, read from the Topic rows
(#886). The court switcher's menu and the sync_corpus command both use it,
so a restart or deploy that keeps the database keeps the switched court."""

import pytest

from litigant_portal.app.models import Topic
from litigant_portal.app.selectors.topic_flow import topic_court_find

pytestmark = [pytest.mark.postgres, pytest.mark.django_db]


def test_topics_all_in_one_court_name_that_court():
    Topic.objects.create(slug="adult-name-change", court="north-dakota")
    Topic.objects.create(slug="minor-name-change", court="north-dakota")
    assert topic_court_find() == "north-dakota"


def test_topics_in_several_courts_name_none():
    Topic.objects.create(slug="adult-name-change", court="north-dakota")
    Topic.objects.create(slug="civil-traffic", court="arizona")
    assert topic_court_find() is None


def test_no_topics_name_none():
    assert topic_court_find() is None


def test_a_topic_without_a_court_is_not_a_court():
    """A topic that predates its first sync has a blank court."""
    Topic.objects.create(slug="legacy", court="")
    assert topic_court_find() is None


def test_a_topic_without_a_court_does_not_hide_the_one_court():
    Topic.objects.create(slug="legacy", court="")
    Topic.objects.create(slug="civil-traffic", court="arizona")
    assert topic_court_find() == "arizona"
