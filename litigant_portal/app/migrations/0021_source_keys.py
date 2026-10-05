from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0020_delete_identity_prompt_artifacts"),
    ]

    operations = [
        migrations.AddField(
            model_name=model_name,
            name="key",
            field=models.SlugField(blank=True, default="", max_length=64),
        )
        for model_name in (
            "contact",
            "resource",
            "topicflowsection",
            "topicflowdeadline",
            "topicflowlink",
        )
    ]
