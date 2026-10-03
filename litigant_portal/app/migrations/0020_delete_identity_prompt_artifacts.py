from django.db import migrations

# The header of the assistant's stored-facts section, which until #958 was
# rendered into the shared system prompt and so into PromptArtifact rows.
FACTS_HEADER = "## Facts the user has already provided"


def _delete_identity_prompt_artifacts(apps, schema_editor):
    """Drop every artifact that holds a person's facts, unlinking its
    messages first because the FK is PROTECT."""
    alias = schema_editor.connection.alias
    PromptArtifact = apps.get_model("app", "PromptArtifact")
    ChatMessage = apps.get_model("app", "ChatMessage")
    artifacts = PromptArtifact.objects.using(alias).filter(
        system_prompt__contains=FACTS_HEADER
    )
    ChatMessage.objects.using(alias).filter(
        prompt_artifact__in=artifacts
    ).update(prompt_artifact=None)
    artifacts.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0019_chatmessage_identity_prompt"),
    ]

    operations = [
        migrations.RunPython(
            _delete_identity_prompt_artifacts,
            migrations.RunPython.noop,
            elidable=True,
        ),
    ]
