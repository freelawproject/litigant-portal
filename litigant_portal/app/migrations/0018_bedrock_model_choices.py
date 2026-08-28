from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0017_corpus_field_types"),
    ]

    operations = [
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
