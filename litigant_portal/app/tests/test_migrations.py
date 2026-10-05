"""Postgres tests that run data migrations for real.

The ``migrator`` fixture rewinds the database to a named migration and hands
back the historical models at that point; plant rows through them, migrate
forward, then assert with the live models. Teardown always returns to head
so the transactional flush and its post_migrate receivers see the current
schema. Add one section per migration under test.
"""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from litigant_portal.app.models import ChatMessage, PromptArtifact

pytestmark = [pytest.mark.postgres, pytest.mark.django_db(transaction=True)]


class Migrator:
    def __init__(self):
        self.executor = MigrationExecutor(connection)

    def migrate(self, name: str):
        self.executor.loader.build_graph()
        self.executor.migrate([("app", name)])

    def rewind(self, name: str):
        """Unapply down to ``name`` and return the historical app registry."""
        self.migrate(name)
        return self.executor.loader.project_state([("app", name)]).apps

    def head(self):
        self.executor.loader.build_graph()
        self.executor.migrate(self.executor.loader.graph.leaf_nodes("app"))


@pytest.fixture
def migrator():
    migrator = Migrator()
    yield migrator
    migrator.head()


# 0020: delete the PromptArtifact rows that captured a person's facts before
# #958 moved them onto the message. Its reverse is a no-op, so the rewind
# involves no DDL.

FACTS_PROMPT = (
    "Be helpful.\n\n## Facts the user has already provided\n\n"
    '- county (County): "Cass" [confirmed]'
)


def test_0020_deletes_facts_artifact_and_unlinks_its_message(migrator):
    apps = migrator.rewind("0019_chatmessage_identity_prompt")
    identity = apps.get_model("app", "UserIdentity").objects.create(
        session_key="migration-958"
    )
    thread = apps.get_model("app", "ChatThread").objects.create(
        identity=identity
    )
    artifact = apps.get_model("app", "PromptArtifact").objects.create(
        system_prompt=FACTS_PROMPT, tool_schemas=[], content_hash="a" * 64
    )
    message = apps.get_model("app", "ChatMessage").objects.create(
        thread=thread,
        data={"role": "assistant", "content": "Answer."},
        prompt_artifact=artifact,
        num_tokens=7,
    )

    migrator.migrate("0020_delete_identity_prompt_artifacts")

    assert not PromptArtifact.objects.filter(id=artifact.id).exists()
    kept = ChatMessage.objects.get(id=message.id)
    assert kept.prompt_artifact_id is None
    assert kept.data["content"] == "Answer."
    assert kept.num_tokens == 7
