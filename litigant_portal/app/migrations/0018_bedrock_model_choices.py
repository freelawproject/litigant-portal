from django.db import migrations, models

# The roster the AlterFields below install. Changing `choices` never touches
# stored data, so a value picked from the old rosters (openai/* or
# bedrock/us.anthropic.*) would survive the migration and then fail at
# litellm — site_get_model only falls back to the default on empty values,
# not stale ones.
BEDROCK_MANTLE_MODELS = [
    "bedrock_mantle/openai.gpt-5.6-luna",
    "bedrock_mantle/openai.gpt-5.6-terra",
    "bedrock_mantle/openai.gpt-5.6-sol",
    "bedrock_mantle/anthropic.claude-haiku-4-5",
    "bedrock_mantle/zai.glm-4.7-flash",
]


def _clear_stale_models(apps, schema_editor):
    """Null out model selections that aren't in the new roster, so the
    site falls back to the default model."""
    Site = apps.get_model("app", "Site")
    sites = Site.objects.using(schema_editor.connection.alias)
    for field in ("fast_model", "assistant_model"):
        sites.exclude(**{f"{field}__in": BEDROCK_MANTLE_MODELS}).update(
            **{field: None}
        )


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0017_corpus_field_types"),
    ]

    operations = [
        migrations.RunPython(
            _clear_stale_models, migrations.RunPython.noop, elidable=True
        ),
        migrations.AlterField(
            model_name="site",
            name="fast_model",
            field=models.CharField(
                blank=True,
                choices=[
                    ("bedrock_mantle/openai.gpt-5.6-luna", "GPT-5.6 Luna"),
                    ("bedrock_mantle/openai.gpt-5.6-terra", "GPT-5.6 Terra"),
                    ("bedrock_mantle/openai.gpt-5.6-sol", "GPT-5.6 Sol"),
                    (
                        "bedrock_mantle/anthropic.claude-haiku-4-5",
                        "Claude Haiku 4.5",
                    ),
                    ("bedrock_mantle/zai.glm-4.7-flash", "GLM 4.7 Flash"),
                ],
                max_length=128,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="site",
            name="assistant_model",
            field=models.CharField(
                blank=True,
                choices=[
                    ("bedrock_mantle/openai.gpt-5.6-luna", "GPT-5.6 Luna"),
                    ("bedrock_mantle/openai.gpt-5.6-terra", "GPT-5.6 Terra"),
                    ("bedrock_mantle/openai.gpt-5.6-sol", "GPT-5.6 Sol"),
                    (
                        "bedrock_mantle/anthropic.claude-haiku-4-5",
                        "Claude Haiku 4.5",
                    ),
                    ("bedrock_mantle/zai.glm-4.7-flash", "GLM 4.7 Flash"),
                ],
                max_length=128,
                null=True,
            ),
        ),
    ]
