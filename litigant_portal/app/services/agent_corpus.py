"""
Connect the deployment's corpus command to the agent catalog publisher.
"""

import asyncio

from django.conf import settings

from lp_agent.adapters.connections import agent_connection
from lp_agent.adapters.db import AgentDatabase
from lp_agent.adapters.session import django_database_dsn
from lp_agent.corpus.sync import AUTHOR, sync_agent_corpus
from lp_agent.types import AccessContext


def agent_corpus_sync(*, court=None, strict=False):
    """
    Publish through deployment credentials after normal Django corpus sync.
    """
    selected_court = settings.CORPUS_COURT if court is None else court

    async def publish():
        async with agent_connection(django_database_dsn()) as connection:
            return await sync_agent_corpus(
                AgentDatabase(connection, AccessContext(identity_id=AUTHOR)),
                settings.BASE_DIR,
                court=selected_court,
                strict=strict,
            )

    return asyncio.run(publish())
