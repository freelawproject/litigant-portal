from functools import wraps

from django.core.cache import cache
from django.db import transaction


def busts_cache(*keys: str):
    """Drop ``keys`` once the surrounding transaction commits.

    Deferring to commit is the point. An immediate delete lets a reader on
    another connection repopulate the key with the pre-commit value, and
    nothing busts it a second time — the stale copy is then permanent,
    because these keys are cached with no timeout.
    """

    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            result = fn(*args, **kwargs)
            transaction.on_commit(lambda: cache.delete_many(keys))
            return result

        return wrapped

    return decorator
