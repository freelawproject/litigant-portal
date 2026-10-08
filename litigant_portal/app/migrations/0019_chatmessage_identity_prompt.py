from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0018_bedrock_model_choices"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatmessage",
            name="identity_prompt",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
