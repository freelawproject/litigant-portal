import logging

from django.core.cache import cache
from django.core.files.storage import storages
from django.db import connection

logger = logging.getLogger(__name__)


def check_database() -> bool:
    """Return True if the default database is reachable."""
    try:
        connection.ensure_connection()
        return connection.is_usable()
    except Exception:
        logger.exception("Health check failed: database unavailable")
        return False


def check_redis() -> bool:
    """Return True if Redis answers a cache set/get round-trip."""
    try:
        cache.set("healthcheck", "ok", timeout=10)
        return cache.get("healthcheck") == "ok"
    except Exception:
        logger.exception("Health check failed: Redis unavailable")
        return False


def check_storage(alias: str) -> bool:
    """Return True if the named storage backend is reachable."""
    try:
        storages[alias].exists("healthcheck")
        return True
    except Exception:
        logger.exception("Health check failed: %r storage unavailable", alias)
        return False
