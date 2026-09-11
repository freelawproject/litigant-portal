"""
Vector corpus search boundary.
"""

from lp_agent.types import SearchHit


async def get_vector_corpus(
    court: str, topic: str, *, query: str
) -> tuple[SearchHit, ...]:
    """
    Search within a court and topic, returning ranked content and provenance.

    The implementation must document its score scale when connected.
    """
    raise NotImplementedError("Vector corpus search is not implemented.")
