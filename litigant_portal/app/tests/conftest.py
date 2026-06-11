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
