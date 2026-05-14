"""Topic Flow registry — (court_slug, topic_slug) → corpus module path.

v1 ships an empty registry; ``has_corpus`` returns False for every pair
so ``portal.views.deep_link`` falls through to the existing chat 302.
Corpora register here as they ship (first one: #397, ND Adult Name
Change).
"""


def has_corpus(court_slug: str, topic_slug: str) -> bool:
    """Return True if a Topic Flow corpus is registered for this pair.

    Skeleton stub — always False until corpora register.
    """
    return False
