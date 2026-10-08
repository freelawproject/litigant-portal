"""The [source:ID] citation grammar and the check for ids a thread never
supplied.

This proves an id was present in the conversation, not that its text
supports the claim next to it; that is the judge's job (#951).
"""

import re
from collections.abc import Iterable

# Python twin of the chip rule in static/js/chat_engine.js (renderInline):
# one or two slash-joined slugs, court/key or topic/flow/key. Change both
# together; the two test files share one list of example ids.
CITATION_PATTERN = re.compile(r"\[source:([a-z0-9_-]+(?:/[a-z0-9_-]+){1,2})\]")
# Any marker at all, well-formed or not. A malformed one shows as raw text
# and can never be a supplied id, so it counts as unknown.
MARKER_PATTERN = re.compile(r"\[source:([^\]]*)\]")


def citation_ids(text: str) -> list[str]:
    """Every well-formed cited id in ``text``, in order, each once."""
    return list(dict.fromkeys(CITATION_PATTERN.findall(text)))


def citation_ids_unknown(text: str, known_ids: Iterable[str]) -> list[str]:
    """The cited ids that are not in ``known_ids``, in order, including
    malformed markers."""
    known = set(known_ids) & set(citation_ids(text))
    markers = dict.fromkeys(MARKER_PATTERN.findall(text))
    return [i for i in markers if i not in known]
