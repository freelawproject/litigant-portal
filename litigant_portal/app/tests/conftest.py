import pytest
from django.core.cache import cache
from django.test import TransactionTestCase

from litigant_portal.app.cache import SITE_CACHE_KEY
from litigant_portal.app.models import Site


@pytest.fixture(autouse=True)
def test_cache(settings):
    """Patch settings to isolate tests from Redis."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
    settings.RATELIMIT_ENABLE = False
    cache.clear()
    yield
    cache.clear()


def _uses_database(request) -> bool:
    if request.node.get_closest_marker("django_db"):
        return True
    if request.cls is not None and issubclass(
        request.cls, TransactionTestCase
    ):
        return True
    return bool({"db", "transactional_db"} & set(request.fixturenames))


@pytest.fixture(autouse=True)
def blank_site_without_a_database(request, test_cache):
    """Serve a blank Site from the cache to tests with no database.

    The court_branding context processor reads the Site row on every page
    render, and a test with no database access would fail on that query.
    A blank Site is what an instance without a court looks like, so the
    header falls back to the Free Law Project logo as it always did.
    """
    if not _uses_database(request):
        cache.set(SITE_CACHE_KEY, Site())


@pytest.fixture(autouse=True)
def test_storage(settings):
    """Use in-memory storage for tests."""
    settings.STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.InMemoryStorage",
        },
        "public": {
            "BACKEND": "django.core.files.storage.InMemoryStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
