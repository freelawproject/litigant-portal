"""
Use the application publisher to populate isolated preparation test databases.
"""

from lp_agent.corpus.sync import sync_agent_corpus


async def load_preparation_fixture(db, resource_root):
    """
    Load real repository corpus without evaluation or conversation fixtures.
    """
    return await sync_agent_corpus(db, resource_root)
