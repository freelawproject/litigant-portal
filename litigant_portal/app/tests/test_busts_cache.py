"""Tests for the busts_cache decorator itself.

Its callers cover the happy path. What they can't show is the failure side:
a service that raises must not schedule the delete, and a delete scheduled
inside a transaction that rolls back must not fire. Both are true by reading
the code; these pin them.

Dedicated keys rather than the real ones, so nothing here depends on the
app's own cached state.
"""

import pytest
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase

from litigant_portal.app.services.utils import busts_cache

KEY_A = "test_busts_a"
KEY_B = "test_busts_b"


@busts_cache(KEY_A, KEY_B)
def _write():
    return "written"


@busts_cache(KEY_A, KEY_B)
def _write_then_fail():
    raise ValueError("service blew up")


def _warm():
    cache.set(KEY_A, "warm", timeout=None)
    cache.set(KEY_B, "warm", timeout=None)


@pytest.mark.postgres
class BustsCacheTests(TestCase):
    def test_a_committed_call_drops_every_key(self):
        _warm()
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(_write(), "written")
        self.assertIsNone(cache.get(KEY_A))
        self.assertIsNone(cache.get(KEY_B))

    def test_the_delete_waits_for_the_commit(self):
        _warm()
        with self.captureOnCommitCallbacks() as callbacks:
            _write()
            self.assertEqual(cache.get(KEY_A), "warm")
        self.assertEqual(len(callbacks), 1)

    def test_a_raising_service_schedules_nothing(self):
        _warm()
        with (
            self.captureOnCommitCallbacks(execute=True) as callbacks,
            self.assertRaises(ValueError),
        ):
            _write_then_fail()
        self.assertEqual(callbacks, [])
        self.assertEqual(cache.get(KEY_A), "warm")
        self.assertEqual(cache.get(KEY_B), "warm")

    def test_a_rolled_back_transaction_leaves_the_cache_warm(self):
        _warm()
        with (
            self.captureOnCommitCallbacks(execute=True) as callbacks,
            self.assertRaises(ValueError),
            transaction.atomic(),
        ):
            _write()
            raise ValueError("caller blew up after the service returned")
        # The write never landed, so the warm copy is still the truth.
        self.assertEqual(callbacks, [])
        self.assertEqual(cache.get(KEY_A), "warm")
