"""
Database corpus retrieval boundary.
"""

from lp_agent.types import CorpusDocument


async def get_database_corpus(
    court: str, topic: str
) -> tuple[CorpusDocument, ...]:
    """
    Retrieve corpus documents for a court and topic from the database.
    """
    raise NotImplementedError("Database corpus retrieval is not implemented.")
