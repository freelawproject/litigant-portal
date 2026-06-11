import pytest


@pytest.fixture(autouse=True)
def test_cache(settings):
    """Patch settings to isolate tests from Redis."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
    settings.RATELIMIT_ENABLE = False


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
