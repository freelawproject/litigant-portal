"""Tests for the post_migrate receivers."""

import weakref
from unittest import mock

import pytest
from django.core.cache import cache
from django.db.models.signals import post_migrate
from django.test import SimpleTestCase, TestCase

from litigant_portal.app.cache import DATA_MODEL_CACHE_KEYS, SITE_CACHE_KEY
from litigant_portal.app.models import Site
from litigant_portal.app.signals import clear_data_model_cache, ensure_site_row


def _connected_receivers() -> list[str]:
    """Names of everything wired to post_migrate, in dispatch order."""
    names = []
    for entry in post_migrate.receivers:
        ref = entry[1]
        fn = ref() if isinstance(ref, weakref.ReferenceType) else ref
        if fn is not None:
            names.append(fn.__name__)
    return names


class ClearDataModelCacheTests(SimpleTestCase):
    def test_every_registered_key_is_dropped(self):
        for key in DATA_MODEL_CACHE_KEYS:
            cache.set(key, "stale", timeout=None)

        clear_data_model_cache(sender=None)

        for key in DATA_MODEL_CACHE_KEYS:
            self.assertIsNone(cache.get(key), key)

    def test_an_unreachable_cache_does_not_abort_the_migrate(self):
        # Redis may be down when migrate runs, and CI has none at all.
        with mock.patch("litigant_portal.app.signals.cache") as fake_cache:
            fake_cache.delete_many.side_effect = ConnectionError("redis down")
            with self.assertLogs("litigant_portal.app.signals", "WARNING"):
                clear_data_model_cache(sender=None)

    def test_it_is_wired_to_run_after_the_row_is_ensured(self):
        # Order matters: the clear has to see whatever the receivers above
        # it wrote. Checks the wiring, not that migrate dispatches it.
        connected = _connected_receivers()
        self.assertIn("clear_data_model_cache", connected)
        self.assertGreater(
            connected.index("clear_data_model_cache"),
            connected.index("ensure_site_row"),
        )


@pytest.mark.postgres
class EnsureSiteRowTests(TestCase):
    def test_it_only_touches_the_row(self):
        # The cache work lives in clear_data_model_cache now.
        cache.set(SITE_CACHE_KEY, "warm", timeout=None)
        Site.objects.all().delete()

        ensure_site_row(sender=None, using="default", apps=None)

        self.assertEqual(Site.objects.count(), 1)
        self.assertEqual(cache.get(SITE_CACHE_KEY), "warm")
