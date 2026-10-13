from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("app", "0026_topicflow_layout"),
    ]

    operations = [
        migrations.AddField(
            model_name="topicflow",
            name="interview_reference",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="topicflow",
            name="interview_prefill",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
