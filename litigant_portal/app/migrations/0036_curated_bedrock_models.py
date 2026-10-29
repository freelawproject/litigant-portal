import warnings

from django.db import migrations, models

MODEL_FIELDS = ("assistant_model", "fast_model", "judge_model")
MODEL_CHOICES = [
    ("auto/openai.luna", "GPT Luna (automatic)"),
    ("auto/openai.terra", "GPT Terra (automatic)"),
    ("auto/openai.sol", "GPT Sol (automatic)"),
    ("auto/anthropic.haiku", "Claude Haiku (automatic)"),
    ("auto/zai.glm-flash", "GLM Flash (automatic)"),
    ("bedrock_mantle/openai.gpt-5.6-luna", "GPT-5.6 Luna"),
    ("bedrock_mantle/openai.gpt-5.6-terra", "GPT-5.6 Terra"),
    ("bedrock_mantle/openai.gpt-5.6-sol", "GPT-5.6 Sol"),
    ("bedrock_mantle/anthropic.claude-haiku-4-5", "Claude Haiku 4.5"),
    ("bedrock_mantle/zai.glm-4.7-flash", "GLM 4.7 Flash"),
    ("tier/economy", "Economy"),
    ("tier/balanced", "Balanced"),
    ("tier/best", "Best"),
]
MODEL_MAPPING = {
    "bedrock_mantle/openai.gpt-5.6-luna": "tier/economy",
    "bedrock_mantle/openai.gpt-5.6-terra": "tier/balanced",
    "bedrock_mantle/openai.gpt-5.6-sol": "tier/best",
    "bedrock_mantle/anthropic.claude-haiku-4-5": "auto/anthropic.haiku",
    "bedrock_mantle/zai.glm-4.7-flash": "auto/zai.glm-flash",
}
REVERSE_MODEL_MAPPING = {
    "tier/economy": "bedrock_mantle/openai.gpt-5.6-luna",
    "tier/balanced": "bedrock_mantle/openai.gpt-5.6-terra",
    "tier/best": "bedrock_mantle/openai.gpt-5.6-sol",
    "auto/openai.luna": "bedrock_mantle/openai.gpt-5.6-luna",
    "auto/openai.terra": "bedrock_mantle/openai.gpt-5.6-terra",
    "auto/openai.sol": "bedrock_mantle/openai.gpt-5.6-sol",
    "auto/zai.glm-flash": "bedrock_mantle/zai.glm-4.7-flash",
}


def migrate_preferences(apps, schema_editor):
    """
    Upgrade known preferences without changing model class or enabling judging.
    """
    sites = apps.get_model("app", "Site").objects.using(
        schema_editor.connection.alias
    )
    known = [value for value, _ in MODEL_CHOICES]
    for field in MODEL_FIELDS:
        if (
            sites.exclude(**{f"{field}__in": [*known, ""]})
            .exclude(**{f"{field}__isnull": True})
            .exists()
        ):
            warnings.warn(
                f"Unrecognized {field} selection retained; select a curated model tier.",
                stacklevel=2,
            )
        for old, new in MODEL_MAPPING.items():
            sites.filter(**{field: old}).update(**{field: new})


def restore_preferences(apps, schema_editor):
    """
    Restore identifiers understood by the previous application version.
    """
    sites = apps.get_model("app", "Site").objects.using(
        schema_editor.connection.alias
    )
    for field in MODEL_FIELDS:
        for new, old in REVERSE_MODEL_MAPPING.items():
            sites.filter(**{field: new}).update(**{field: old})


class Migration(migrations.Migration):
    dependencies = [("app", "0035_haiku_model_discovery")]
    operations = [
        migrations.RunPython(migrate_preferences, restore_preferences),
        *[
            migrations.AlterField(
                model_name="site",
                name=field,
                field=models.CharField(
                    blank=True,
                    choices=MODEL_CHOICES,
                    max_length=128,
                    null=True,
                ),
            )
            for field in MODEL_FIELDS
        ],
    ]
