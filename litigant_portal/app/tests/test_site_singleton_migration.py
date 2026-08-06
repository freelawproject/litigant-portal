"""Tests for migration 0012, which collapses Site to a single row.

_prune_extra_sites and _pin_site_pk are the only new logic in 0012, and
test_site_singleton.py checks the state they leave behind rather than the
steps themselves. These drive the migration for real.

TransactionTestCase because migrating is DDL and cannot be rolled back.
Each test rewinds to 0011, plants rows, migrates forward, asserts. tearDown
always returns to head -- it runs before the flush, so the flush and its
post_migrate receivers see the current schema.
"""

from datetime import timedelta

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone

from litigant_portal.app.models import Site, Topic
from litigant_portal.app.models.site import SITE_ID

MIGRATE_FROM = ("app", "0011_site_permissions_delete_sitemembership")
MIGRATE_TO = ("app", "0012_site_singleton")


@pytest.mark.postgres
class SiteSingletonMigrationTests(TransactionTestCase):
    def tearDown(self):
        self._migrate(MIGRATE_TO)

    def _migrate(self, target):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([target])
        return executor

    def _rewind(self):
        """Unapply 0012 and hand back the historical models at 0011.

        Emptying first is required, not tidiness. Reversing 0012 re-adds
        Site.name (NOT NULL, blank=False, so the schema editor substitutes
        NULL rather than "") and Topic.site (NOT NULL FK), and both ALTERs
        fail on a table with rows. ensure_site_row plants a Site row on every
        migrate and on every TransactionTestCase flush, so there is always
        one waiting.
        """
        Topic.objects.all().delete()
        Site.objects.all().delete()
        executor = self._migrate(MIGRATE_FROM)
        apps = executor.loader.project_state([MIGRATE_FROM]).apps
        return apps.get_model("app", "Site"), apps.get_model("app", "Topic")

    def _backdate(self, model, pk, days):
        """created_at is auto_now_add, so it can only be set after the fact."""
        model.objects.filter(pk=pk).update(
            created_at=timezone.now() - timedelta(days=days)
        )

    def test_the_active_site_survives_and_takes_the_singleton_id(self):
        old_site, old_topic = self._rewind()
        stale = old_site.objects.create(name="stale", active=False)
        old_topic.objects.create(
            site=stale, slug="eviction", title="Stale Evictions", order=0
        )
        live = old_site.objects.create(name="live", active=True)
        old_topic.objects.create(
            site=live, slug="eviction", title="Live Evictions", order=0
        )
        # The uuid4 that seed_data minted, which 0012 has to repoint.
        self.assertNotEqual(live.id, SITE_ID)

        self._migrate(MIGRATE_TO)

        self.assertEqual(Site.objects.count(), 1)
        self.assertEqual(Site.objects.get().id, SITE_ID)
        # The slug collided across the two sites, so this also pins the
        # ordering: pruning has to happen before slug goes unique.
        self.assertEqual(
            list(Topic.objects.values_list("title", flat=True)),
            ["Live Evictions"],
        )

    def test_the_oldest_site_wins_when_none_is_active(self):
        old_site, old_topic = self._rewind()
        first = old_site.objects.create(name="first", active=False)
        old_topic.objects.create(
            site=first, slug="eviction", title="First", order=0
        )
        second = old_site.objects.create(name="second", active=False)
        old_topic.objects.create(
            site=second, slug="eviction", title="Second", order=0
        )
        self._backdate(old_site, first.pk, days=2)
        self._backdate(old_site, second.pk, days=1)

        self._migrate(MIGRATE_TO)

        self.assertEqual(Site.objects.count(), 1)
        self.assertEqual(Topic.objects.get().title, "First")

    def test_an_empty_table_gets_the_singleton_row(self):
        old_site, _ = self._rewind()
        self.assertEqual(old_site.objects.count(), 0)

        self._migrate(MIGRATE_TO)

        self.assertEqual(Site.objects.count(), 1)
        self.assertEqual(Site.objects.get().id, SITE_ID)
