from functools import wraps

from django.core.cache import cache
from django.db import transaction
from django.utils.text import slugify


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


def row_move(rows: list, row, direction: str) -> None:
    """Swap ``row`` with its neighbor and renumber ``order`` sequentially."""
    idx = rows.index(row)
    swap = idx - 1 if direction == "up" else idx + 1
    if swap < 0 or swap >= len(rows):
        return
    rows[idx], rows[swap] = rows[swap], rows[idx]
    for position, obj in enumerate(rows):
        if obj.order != position:
            obj.order = position
            obj.save(update_fields=["order", "updated_at"])


def unique_slug(queryset, name: str, fallback: str) -> str:
    """Slugify ``name``, suffixing ``-2``, ``-3``, … until unique within
    ``queryset``."""
    base = slugify(name)[:64] or fallback
    slug, n = base, 2
    while queryset.filter(slug=slug).exists():
        suffix = f"-{n}"
        slug, n = base[: 64 - len(suffix)] + suffix, n + 1
    return slug
