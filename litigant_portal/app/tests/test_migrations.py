"""Postgres tests that run data migrations for real.

The ``migrator`` fixture rewinds the database to a named migration and hands
back the historical models at that point; plant rows through them, migrate
forward, then assert with the live models. Teardown always returns to head
so the transactional flush and its post_migrate receivers see the current
schema. Add one section per migration under test.
"""

import pytest
from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
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


# 0037: the tiered roles (#1135). Admins becomes FLP Staff, User admins
# becomes Court Admins, and Developers folds into FLP Staff. Membership must
# carry over: a court's account that loses its group loses its access.


def test_0037_carries_role_membership_into_the_renamed_groups(migrator):
    migrator.rewind("0036_bedrock_model_choices")
    # Planted with the live auth models: 0036's historical registry stops
    # short of contenttypes' own later migrations (its ContentType still
    # has a ``name`` column), and none of these tables change with ours.
    # Rewinding runs no post_migrate, so the head's groups are still here;
    # clear them to plant the world as 0036 left it.
    Group.objects.all().delete()
    admins = Group.objects.create(name="Admins")
    developers = Group.objects.create(name="Developers")
    user_admins = Group.objects.create(name="User admins")
    admin = User.objects.create_user(username="admin")
    developer = User.objects.create_user(username="developer")
    both = User.objects.create_user(username="both")
    court = User.objects.create_user(username="court")
    admin.groups.add(admins)
    developer.groups.add(developers)
    both.groups.add(admins, developers)
    court.groups.add(user_admins)
    # The permission 0034 declared; post_migrate never recreates it at head.
    Permission.objects.get_or_create(
        codename="manage_developers",
        content_type=ContentType.objects.get(app_label="app", model="site"),
        defaults={"name": "Can manage developer access"},
    )

    migrator.migrate("0037_tiered_admin_roles")

    assert sorted(Group.objects.values_list("name", flat=True)) == [
        "Court Admins",
        "FLP Staff",
    ]
    staff = Group.objects.get(name="FLP Staff")
    assert sorted(staff.user_set.values_list("username", flat=True)) == [
        "admin",
        "both",
        "developer",
    ]
    assert list(
        Group.objects.get(name="Court Admins").user_set.values_list(
            "username", flat=True
        )
    ) == ["court"]
    assert not Permission.objects.filter(codename="manage_developers").exists()
