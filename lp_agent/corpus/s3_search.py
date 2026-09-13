"""
S3 corpus retrieval boundary.
"""

from lp_agent.types import CorpusDocument


async def get_s3_corpus(court: str, topic: str) -> tuple[CorpusDocument, ...]:
    """
    Retrieve corpus documents for a court and topic from S3.
    """
    raise NotImplementedError("S3 corpus retrieval is not implemented.")
