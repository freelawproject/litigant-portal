import warnings

from django.db import migrations, models

from lp_agent.adapters.bedrock_models import model_choices

MODEL_FIELDS = ("assistant_model", "fast_model", "judge_model")
MODEL_MAPPING = {
    "bedrock_mantle/openai.gpt-5.6-luna": "auto/openai.luna",
    "bedrock_mantle/openai.gpt-5.6-terra": "auto/openai.terra",
    "bedrock_mantle/openai.gpt-5.6-sol": "auto/openai.sol",
    "bedrock_mantle/anthropic.claude-haiku-4-5": "auto/anthropic.haiku",
    "bedrock_mantle/zai.glm-4.7-flash": "auto/zai.glm-flash",
}


def migrate_preferences(apps, schema_editor):
    """
    Preserve model families and disabled judging when upgrading from main.
    """
    sites = apps.get_model("app", "Site").objects.using(
        schema_editor.connection.alias
    )
    known = [*MODEL_MAPPING, *MODEL_MAPPING.values(), ""]
    for field in MODEL_FIELDS:
        if (
            sites.exclude(**{f"{field}__in": known})
            .exclude(**{f"{field}__isnull": True})
            .exists()
        ):
            warnings.warn(
                f"Unrecognized {field} selection retained; choose an enabled model.",
                stacklevel=2,
            )
        for old, new in MODEL_MAPPING.items():
            sites.filter(**{field: old}).update(**{field: new})


def restore_preferences(apps, schema_editor):
    """
    Restore the identifiers supported before model discovery.
    """
    sites = apps.get_model("app", "Site").objects.using(
        schema_editor.connection.alias
    )
    for field in MODEL_FIELDS:
        for old, new in MODEL_MAPPING.items():
            sites.filter(**{field: new}).update(**{field: old})


class Migration(migrations.Migration):
    dependencies = [("app", "0034_topicflowinterviewpage_on_page")]
    operations = [
        migrations.RunPython(migrate_preferences, restore_preferences),
        *[
            migrations.AlterField(
                model_name="site",
                name=field,
                field=models.CharField(
                    blank=True,
                    choices=model_choices,
                    max_length=128,
                    null=True,
                ),
            )
            for field in MODEL_FIELDS
        ],
    ]
