"""Tests for the Site singleton and its cache.

Three invariants: the row always exists, a second row is impossible, and
the cached copy never outlives a committed write. The last one is the
subtle case — invalidation is deferred to commit, so the cache stays warm
inside an open transaction and is dropped only once it lands.
"""

import uuid

import pytest
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.test import TestCase

from litigant_portal.app.cache import SITE_CACHE_KEY, TOPIC_LIST_CACHE_KEY
from litigant_portal.app.models import Site, Topic
from litigant_portal.app.models.site import SITE_ID
from litigant_portal.app.selectors.site import site_get, site_get_model
from litigant_portal.app.selectors.topic_flow import topic_list
from litigant_portal.app.services.site import site_update
from litigant_portal.app.services.topic_flow import topic_create


@pytest.mark.postgres
class SingletonRowTests(TestCase):
    def test_the_row_exists_and_is_pinned(self):
        # Created by the post_migrate receiver, not by any test fixture.
        self.assertEqual(Site.objects.count(), 1)
        self.assertEqual(Site.objects.get().id, SITE_ID)

    def test_a_second_row_is_rejected_by_the_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Site.objects.create(id=uuid.uuid4())

    def test_a_second_row_is_rejected_even_at_the_pinned_id(self):
        # The primary key blocks this one rather than the check constraint,
        # but the outcome callers depend on is the same.
        with self.assertRaises(IntegrityError), transaction.atomic():
            Site.objects.create(id=SITE_ID)

    def test_site_get_needs_no_arguments(self):
        self.assertEqual(site_get().id, SITE_ID)


@pytest.mark.postgres
class SiteCacheTests(TestCase):
    def setUp(self):
        cache.delete(SITE_CACHE_KEY)

    def test_site_get_populates_the_cache(self):
        self.assertIsNone(cache.get(SITE_CACHE_KEY))
        site_get()
        self.assertIsNotNone(cache.get(SITE_CACHE_KEY))

    def test_a_committed_write_drops_the_cached_copy(self):
        site_get()
        # captureOnCommitCallbacks is required: TestCase wraps each test in a
        # transaction that never commits, so on_commit hooks would otherwise
        # never run and this would pass for the wrong reason.
        with self.captureOnCommitCallbacks(execute=True):
            site_update(site=Site.objects.get(), court_name="Cass County")
        self.assertIsNone(cache.get(SITE_CACHE_KEY))
        self.assertEqual(site_get().court_name, "Cass County")

    def test_invalidation_is_deferred_until_commit(self):
        site_get()
        with self.captureOnCommitCallbacks() as callbacks:
            site_update(site=Site.objects.get(), court_name="Pending")
            # Queued, not run: a reader racing this transaction must not be
            # able to repopulate the cache from an uncommitted row.
            self.assertIsNotNone(cache.get(SITE_CACHE_KEY))
        self.assertEqual(len(callbacks), 1)

    def test_site_get_model_falls_back_when_unset(self):
        site_update(site=Site.objects.get(), assistant_model="")
        self.assertTrue(site_get_model(role="assistant"))


@pytest.mark.postgres
class TopicScopingTests(TestCase):
    """Topics are no longer scoped to a site."""

    def setUp(self):
        cache.delete(TOPIC_LIST_CACHE_KEY)

    def test_topic_needs_no_site(self):
        topic = topic_create(title="Evictions")
        self.assertEqual(topic.slug, "evictions")

    def test_slug_is_globally_unique(self):
        topic_create(title="Evictions")
        second = topic_create(title="Evictions")
        self.assertEqual(second.slug, "evictions-2")

    def test_duplicate_slug_is_rejected_by_the_database(self):
        topic_create(title="Evictions")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Topic.objects.create(slug="evictions", title="Clash")

    def test_topic_list_is_cached_and_busted_by_writes(self):
        topic_list()
        self.assertIsNotNone(cache.get(TOPIC_LIST_CACHE_KEY))

        with self.captureOnCommitCallbacks(execute=True):
            topic_create(title="Small Claims")
        self.assertIsNone(cache.get(TOPIC_LIST_CACHE_KEY))
        self.assertEqual(len(topic_list()), 1)
